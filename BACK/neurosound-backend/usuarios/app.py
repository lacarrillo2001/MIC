import re
from typing import Literal

from bson import ObjectId
from fastapi import HTTPException, Request
from pydantic import Field
from pymongo import ReturnDocument

from shared.runtime import (Model, clean, config, create_app, dbof, ensure_owner, get_document,
                            identity, internal, now, oid, password_hash, password_valid, peer, token)

CONSENT_VERSION = "consentimiento-v1"


class Register(Model):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    mayor_edad_confirmado: Literal[True]
    consentimiento_aceptado: Literal[True]
    consentimiento_version: Literal["consentimiento-v1"]


class Login(Model):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class Preferences(Model):
    version_esperada: int = Field(ge=1)
    artistas_preferidos: list[str] = Field(default_factory=list, max_length=3)
    generos_preferidos: list[str] = Field(default_factory=list, max_length=3)
    tempo_preferido: Literal["lento", "moderado", "rapido"] | None = None
    preferencia_voz: Literal['instrumental', 'con_voz'] | None = None


class ToneAnswer(Model):
    tono_id: str = Field(max_length=80)
    audio_id: str
    frecuencia_hz: float = Field(gt=0, le=20000)
    orden: int = Field(ge=1, le=30)
    agrado: float | None = None
    molestia: float | None = None
    omitido: bool = False


class ToneFinish(Model):
    estado: Literal["completada", "interrumpida"]
    respuestas: list[ToneAnswer] = Field(max_length=30)


class Adjustment(Model):
    feedback_id: str
    version_esperada: int = Field(ge=1)
    atributos: dict[str, float]


def participant(db, user_id):
    user = get_document(db.usuarios, user_id)
    if user["estado"] != "activo" or not user["mayor_edad_confirmado"] or not user["consentimiento"]["aceptado"]:
        raise HTTPException(403, "Participación no autorizada o consentimiento retirado")
    return user


def profile(db, user_id):
    item = db.perfiles.find_one({"usuario_id": oid(user_id)})
    if not item:
        # Reparación idempotente si el proceso se detuvo después del registro.
        db.perfiles.update_one({"usuario_id": oid(user_id)}, {"$setOnInsert": {
            "artistas_preferidos": [], "generos_preferidos": [], "tempo_preferido": None,
            "afinidad_aprendida": {}, "feedback_aplicados": [], "version": 1, "actualizado_en": now()}}, upsert=True)
        item = db.perfiles.find_one({"usuario_id": oid(user_id)})
    return item


def profile_public(item):
    return clean({k: v for k, v in item.items() if k != "feedback_aplicados"})


def build_app(db=None, peer_override=None):
    app = create_app("usuarios", db, peer_override)

    @app.post("/auth/registro", status_code=201)
    def register(body: Register, request: Request):
        email = body.email.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise HTTPException(422, "Correo inválido")
        data = {"email": email, "password_hash": password_hash(body.password), "rol": "estudiante",
                "mayor_edad_confirmado": True, "consentimiento": {"aceptado": True,
                "version": CONSENT_VERSION, "aceptado_en": now()}, "estado": "activo", "creado_en": now()}
        result = dbof(request).usuarios.insert_one(data)
        profile(dbof(request), str(result.inserted_id))
        return {"usuario_id": str(result.inserted_id)}

    @app.post("/auth/login")
    def login(body: Login, request: Request):
        user = dbof(request).usuarios.find_one({"email": body.email.strip().lower()})
        # El mismo trabajo criptográfico para cuentas inexistentes.
        encoded = user["password_hash"] if user else "00" * 16 + ":" + "00" * 64
        valid = password_valid(body.password, encoded)
        if not user or not valid:
            raise HTTPException(401, "Credenciales inválidas")
        participant(dbof(request), str(user["_id"]))
        return {"access_token": token(user["_id"], role=user["rol"]), "token_type": "bearer", "expires_in": 7200}

    @app.get("/usuarios/me")
    def me(request: Request):
        user = participant(dbof(request), identity(request)["sub"])
        return clean({k: v for k, v in user.items() if k != "password_hash"})

    @app.post("/usuarios/me/retiro")
    def withdraw(request: Request):
        user = identity(request)
        dbof(request).usuarios.update_one({"_id": oid(user["sub"])}, {"$set": {
            "estado": "retirado", "consentimiento.aceptado": False, "consentimiento.retirado_en": now()}})
        return {"estado": "retirado", "nota": "No se han eliminado registros; aplicar la política de conservación del estudio"}

    @app.get("/perfiles/me")
    def my_profile(request: Request):
        user = identity(request)
        participant(dbof(request), user["sub"])
        return profile_public(profile(dbof(request), user["sub"]))

    @app.put("/perfiles/me")
    def preferences(body: Preferences, request: Request):
        user = identity(request)
        database = dbof(request)
        participant(database, user["sub"])
        if any(not x or len(x) > 100 for x in body.artistas_preferidos + body.generos_preferidos):
            raise HTTPException(422, "IDs o géneros inválidos")
        if body.artistas_preferidos:
            peer(request, "recomendacion", "POST", "/internal/artistas/validar", {"ids": body.artistas_preferidos})
        genres = peer(request, 'recomendacion', 'POST', '/internal/generos/resolver', {'generos': body.generos_preferidos})
        if genres['no_reconocidos']:
            raise HTTPException(422, 'Géneros no reconocidos: ' + ', '.join(genres['no_reconocidos']) + '. Selecciona una etiqueta de las sugerencias del catálogo.')
        result = database.perfiles.find_one_and_update(
            {"usuario_id": oid(user["sub"]), "version": body.version_esperada},
            {"$set": {"artistas_preferidos": sorted(set(body.artistas_preferidos)),
                      "generos_preferidos": genres['generos'],
                      "tempo_preferido": body.tempo_preferido, "preferencia_voz": body.preferencia_voz,
                      "cuestionario_version": "perfil-musical-v2", "actualizado_en": now()}, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER)
        if not result:
            raise HTTPException(409, "Perfil modificado; consultar su versión actual")
        return profile_public(result)

    @app.get("/tonos/configuracion")
    def tone_configuration(request: Request):
        participant(dbof(request), identity(request)["sub"])
        return config("tonos-v1")

    @app.post("/evaluaciones-tonos", status_code=201)
    def start_tones(request: Request):
        user = identity(request)
        participant(dbof(request), user["sub"])
        cfg = config("tonos-v1")
        if not cfg["aprobado"] or any(not x["duracion_ms"] for x in cfg["tonos"]):
            raise HTTPException(503, "Protocolo de tonos pendiente de aprobación y duración")
        audios = peer(request, "sesiones", "POST", "/internal/audios/tonos", {"tono_ids": [x["tono_id"] for x in cfg["tonos"]]})
        if set(audios) != {x["tono_id"] for x in cfg["tonos"]}:
            raise HTTPException(409, "Faltan audios de tonos verificados")
        for item in cfg["tonos"]:
            if audios[item["tono_id"]]["duracion_ms"] != item["duracion_ms"]:
                raise HTTPException(409, "La duración del audio no coincide con el protocolo")
        data = {"usuario_id": oid(user["sub"]), "configuracion_version": cfg["version"],
                "configuracion_utilizada": cfg, "audios_utilizados": audios, "respuestas": [],
                "estado": "en_curso", "creado_en": now()}
        dbof(request).evaluaciones_tonos.insert_one(data)
        return clean(data)

    @app.put("/evaluaciones-tonos/{evaluation_id}")
    def finish_tones(evaluation_id: str, body: ToneFinish, request: Request):
        database = dbof(request)
        user = identity(request)
        participant(database, user["sub"])
        item = get_document(database.evaluaciones_tonos, evaluation_id)
        ensure_owner(item, user)
        cfg = item["configuracion_utilizada"]
        definitions = {x["tono_id"]: x for x in cfg["tonos"]}
        ids, orders = set(), set()
        for answer in body.respuestas:
            tone = definitions.get(answer.tono_id)
            if not tone or answer.tono_id in ids or answer.orden in orders:
                raise HTTPException(422, "Tonos u orden inválidos o repetidos")
            ids.add(answer.tono_id)
            orders.add(answer.orden)
            if answer.frecuencia_hz != tone["frecuencia_hz"] or answer.audio_id != item["audios_utilizados"][answer.tono_id]["audio_id"]:
                raise HTTPException(422, "Audio o frecuencia no coincide con el tono configurado")
            values = [answer.agrado, answer.molestia]
            if answer.omitido:
                if any(x is not None for x in values):
                    raise HTTPException(422, "Una omisión no tiene puntuaciones")
            elif any(x is None or not cfg["escala"]["min"] <= x <= cfg["escala"]["max"] for x in values):
                raise HTTPException(422, "Valoración fuera de escala")
        if body.estado == "completada" and ids != set(definitions):
            raise HTTPException(422, "Faltan respuestas u omisiones de tonos")
        payload = body.model_dump()
        if item["estado"] != "en_curso":
            if item["estado"] == body.estado and item["respuestas"] == payload["respuestas"]:
                return clean(item)
            raise HTTPException(409, "Evaluación ya cerrada")
        updated = database.evaluaciones_tonos.find_one_and_update({"_id": item["_id"], "estado": "en_curso"},
            {"$set": {**payload, "finalizado_en": now()}}, return_document=ReturnDocument.AFTER)
        if not updated:
            raise HTTPException(409, "Evaluación modificada concurrentemente")
        return clean(updated)

    @app.get("/internal/usuarios/{user_id}/contexto")
    def context(user_id: str, request: Request):
        internal(request, {"sesiones", "recomendacion"})
        user = participant(dbof(request), user_id)
        evaluation = dbof(request).evaluaciones_tonos.find_one({"usuario_id": oid(user_id), "estado": "completada"}, sort=[("creado_en", -1)])
        return {"usuario_id": user_id, "rol": user["rol"], "consentimiento_version": user["consentimiento"]["version"],
                "perfil": profile_public(profile(dbof(request), user_id)), "evaluacion_tonos": clean(evaluation)}

    @app.get("/internal/evaluaciones/{evaluation_id}")
    def evaluation(evaluation_id: str, request: Request):
        internal(request, {"sesiones", "recomendacion"})
        item = get_document(dbof(request).evaluaciones_tonos, evaluation_id)
        participant(dbof(request), str(item["usuario_id"]))
        return clean(item)

    @app.post("/internal/perfiles/{user_id}/ajustes")
    def adjustment(user_id: str, body: Adjustment, request: Request):
        internal(request, {"recomendacion"})
        database = dbof(request)
        participant(database, user_id)
        item = profile(database, user_id)
        oid(body.feedback_id)
        if body.feedback_id in item["feedback_aplicados"]:
            return {"aplicado": True, "duplicado": True, "version": item["version"]}
        if not body.atributos or set(body.atributos) - {"energy", "valence"} or any(not 0 <= x <= 1 for x in body.atributos.values()):
            raise HTTPException(422, "Afinidades fuera de rango")
        result = database.perfiles.find_one_and_update({"usuario_id": oid(user_id), "version": body.version_esperada,
            "feedback_aplicados": {"$ne": body.feedback_id}}, {"$set": {
                **{f"afinidad_aprendida.{k}": v for k, v in body.atributos.items()}, "actualizado_en": now()},
                "$inc": {"version": 1}, "$addToSet": {"feedback_aplicados": body.feedback_id}}, return_document=ReturnDocument.AFTER)
        if not result:
            # Otra petición pudo aplicar el mismo feedback mientras leíamos.
            current = profile(database, user_id)
            if body.feedback_id in current["feedback_aplicados"]:
                return {"aplicado": True, "duplicado": True, "version": current["version"]}
            raise HTTPException(409, "Conflicto de versión del perfil")
        return {"aplicado": True, "duplicado": False, "version": result["version"]}
    return app


app = build_app()
