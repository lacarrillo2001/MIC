"""Infraestructura mínima compartida; cada servicio conserva sus colecciones."""
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
from bson import ObjectId
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pymongo import ASCENDING, MongoClient
from pymongo.errors import CollectionInvalid, DuplicateKeyError, OperationFailure, PyMongoError

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ("usuarios", "recomendacion", "sesiones")
COLLECTIONS = {
    "usuarios": {"usuarios": [("email", True)], "perfiles": [("usuario_id", True)],
                 "evaluaciones_tonos": [("usuario_id", False)]},
    "recomendacion": {"songsV2": [("id", False), ("idros", False)], "artists": [("id", False)],
                      "youtube_vinculos": [("track_id", True)],
                      "recomendaciones": [([("usuario_id", 1), ("solicitud_id", 1)], True), ("sesion_id", False)],
                      "feedback": [([("usuario_id", 1), ("solicitud_id", 1)], True), ("sesion_id", False)]},
    "sesiones": {"audios": [("track_id", False), ("tono_id", False)],
                 "sesiones": [("usuario_id", False), ([("usuario_id", 1), ("solicitud_id", 1)], True)],
                 "encuestas": [("sesion_id", True)]},
}


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def now():
    return datetime.now(timezone.utc)


def config(name):
    return json.loads((ROOT / "config" / f"{name}.json").read_text(encoding="utf-8"))


def oid(value):
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(422, "Identificador inválido")


def clean(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(clean(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def initialize(db, service):
    """También se ejecuta en reinicios. No elimina ni reemplaza documentos."""
    for collection, indexes in COLLECTIONS[service].items():
        try:
            db.create_collection(collection, check_exists=False)
        except CollectionInvalid:
            pass
        except OperationFailure as exc:
            if exc.code != 48:  # NamespaceExists, no ignorar otros fallos
                raise
        for fields, unique in indexes:
            keys = [(fields, ASCENDING)] if isinstance(fields, str) else fields
            db[collection].create_index(keys, unique=unique)
    if service == "recomendacion":
        db.youtube_vinculos.create_index("caduca_en", expireAfterSeconds=0)


def secret(name):
    value = os.environ.get(name, "")
    if len(value) < 32 or value.startswith("REEMPLAZAR"):
        raise RuntimeError(f"Configurar {name} con al menos 32 caracteres aleatorios")
    return value


def token(user_id, *, role="estudiante", session_id=None):
    payload = {"sub": str(user_id), "rol": role, "iat": now(),
               "exp": now() + timedelta(minutes=30 if session_id else 120),
               "iss": "neurosound", "aud": "sala" if session_id else "web"}
    if session_id:
        payload["sesion_id"] = session_id
    return jwt.encode(payload, secret("JWT_SECRET"), algorithm="HS256")


def identity(request: Request, allow_room=False):
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Se requiere token Bearer")
    try:
        data = jwt.decode(authorization[7:], secret("JWT_SECRET"), algorithms=["HS256"],
                          issuer="neurosound", audience=["web", "sala"] if allow_room else "web",
                          options={"require": ["exp", "iat", "sub", "aud", "iss"]})
        oid(data["sub"])
        return data
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(401, "Token inválido o vencido")


def internal(request: Request, allowed):
    caller = request.headers.get("x-service-name", "")
    provided = request.headers.get("x-service-key", "")
    if caller not in allowed or not hmac.compare_digest(provided, secret(f"{caller.upper()}_SERVICE_KEY")):
        raise HTTPException(403, "Acceso interno no autorizado")


def peer(request, target, method, path, body=None):
    if request.app.state.peer_override:
        return request.app.state.peer_override(target, method, path, body)
    name = request.app.state.service
    try:
        response = httpx.request(method, os.environ[f"{target.upper()}_URL"] + path,
                                 json=body, timeout=10,
                                 headers={"X-Service-Name": name,
                                          "X-Service-Key": secret(f"{name.upper()}_SERVICE_KEY")})
    except httpx.RequestError:
        raise HTTPException(503, f"Servicio {target} no disponible")
    if response.is_error:
        # No divulgar trazas ni secretos de otros servicios.
        detail = response.json().get("detail", "Operación rechazada") if "json" in response.headers.get("content-type", "") else "Operación rechazada"
        raise HTTPException(response.status_code, detail)
    return response.json()


def dbof(request):
    return request.app.state.db


def get_document(collection, identifier):
    result = collection.find_one({"_id": oid(identifier)})
    if not result:
        raise HTTPException(404, "Recurso no encontrado")
    return result


def ensure_owner(document, user):
    if str(document["usuario_id"]) != user["sub"]:
        raise HTTPException(403, "El recurso pertenece a otro usuario")


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def password_valid(password, encoded):
    salt, expected = encoded.split(":")
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(actual, expected)


def create_app(service, db=None, peer_override=None):
    @asynccontextmanager
    async def lifespan(app):
        secret("JWT_SECRET")
        for item in SERVICES:
            secret(f"{item.upper()}_SERVICE_KEY")
        client = None
        if db is None:
            client = MongoClient(host=os.environ["MONGO_HOST"], username=os.environ["MONGO_USER"],
                                 password=os.environ["MONGO_PASSWORD"],
                                 authSource=os.environ.get("MONGO_DATABASE", "neurosound"),
                                 serverSelectionTimeoutMS=2000, connectTimeoutMS=2000, tz_aware=True)
            for attempt in range(10):
                try:
                    client.admin.command("ping")
                    break
                except PyMongoError:
                    if attempt == 9:
                        client.close()
                        raise RuntimeError("MongoDB no disponible; inicio cancelado") from None
                    time.sleep(1)
            app.state.db = client[os.environ.get("MONGO_DATABASE", "neurosound")]
        else:
            app.state.db = db
        try:
            initialize(app.state.db, service)
            if service == "recomendacion" and os.environ.get("CATALOGUE_AUTO_IMPORT", "false").lower() == "true":
                from shared.catalogue import auto_import
                app.state.catalogue_import = auto_import(app.state.db)
            app.state.ready = True
            yield
        finally:
            app.state.ready = False
            if client:
                client.close()

    app = FastAPI(title=f"NeuroSound · {service}", version="0.1.0", lifespan=lifespan)
    app.state.service = service
    app.state.peer_override = peer_override
    app.state.ready = False
    @app.middleware("http")
    async def bounded_body(request, call_next):
        # Evita cuerpos grandes, incluso cuando llegan fragmentados sin Content-Length.
        if request.method in {"POST", "PUT"}:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    return JSONResponse(status_code=413, content={"detail": "Cuerpo máximo: 64 KiB"})
            request._body = bytes(body)
        return await call_next(request)
    app.add_middleware(CORSMiddleware,
                       allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Authorization", "Content-Type", "Range"],
                       expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"])

    @app.exception_handler(DuplicateKeyError)
    async def duplicate_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": "El registro ya existe; consultar o reenviar con el mismo identificador"})

    @app.exception_handler(PyMongoError)
    async def mongo_handler(request, exc):
        return JSONResponse(status_code=503, content={"detail": "Almacenamiento temporalmente no disponible"})

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "alive", "service": service}

    @app.get("/health/ready", tags=["health"])
    def ready(request: Request):
        if not app.state.ready:
            raise HTTPException(503, "Inicialización pendiente")
        dbof(request).command("ping")
        return {"status": "ready", "service": service}
    return app
