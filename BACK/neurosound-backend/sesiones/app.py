import hashlib
import os
import secrets
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import Field
from pymongo import ReturnDocument

from shared.runtime import (Model, clean, config, create_app, dbof, ensure_owner, fingerprint,
                            get_document, identity, internal, now, oid, peer, token)


class SessionInput(Model):
    solicitud_id: str = Field(min_length=8, max_length=100)
    actividad: dict[str, str] = Field(min_length=1, max_length=12)
    modalidad: Literal["personalizada", "personalizada_heuristica"] = "personalizada"


class Exchange(Model):
    codigo: str = Field(min_length=40, max_length=100)


class StateInput(Model):
    estado: Literal["activa", "pausada", "finalizada", "interrumpida"]


class EventData(Model):
    track_id: str = Field(max_length=100)
    audio_id: str
    recomendacion_id: str
    reproduccion_id: str = Field(min_length=8, max_length=100)
    posicion_ms: int = Field(ge=0)
    volumen: float = Field(ge=0, le=1)
    error: str | None = Field(default=None, max_length=300)


class PlaybackEvent(Model):
    evento_id: str = Field(min_length=8, max_length=100)
    tipo: Literal["reproduccion_inicio", "reproduccion_pausa", "reproduccion_fin", "omision", "volumen", "error"]
    ocurrido_en: datetime
    datos: EventData


class AudioInput(Model):
    tipo: Literal["cancion", "tono"]
    track_id: str | None = Field(default=None, max_length=100)
    tono_id: str | None = Field(default=None, max_length=100)
    ubicacion: str = Field(min_length=1, max_length=300)
    correspondencia_verificada: Literal[True]
    fuente_autorizada: Literal[True]


class SurveyAnswer(Model):
    pregunta_id: str = Field(max_length=100)
    valor: float


class SurveyInput(Model):
    cuestionario_version: str = Field(max_length=100)
    respuestas: list[SurveyAnswer] = Field(max_length=30)


class TrackIds(Model):
    track_ids: list[str] = Field(max_length=1000)


class ToneIds(Model):
    tono_ids: list[str] = Field(max_length=30)


class LinkInput(Model):
    recomendacion_id: str


def safe_path(location):
    root = Path(os.environ.get("MEDIA_ROOT", "media")).resolve()
    relative = Path(location)
    target = (root / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(root) or target == root:
        raise HTTPException(422, "Ruta de audio fuera del directorio permitido")
    if not target.is_file():
        raise HTTPException(404, "Archivo de audio no disponible")
    return target


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def available(audio):
    if not audio.get("fuente_autorizada") or not audio.get("correspondencia_verificada"):
        return False
    try:
        return file_hash(safe_path(audio["ubicacion"])) == audio["hash_archivo"]
    except (HTTPException, OSError):
        return False


def web_participant(request):
    user = identity(request)
    context = peer(request, "usuarios", "GET", f"/internal/usuarios/{user['sub']}/contexto")
    return user, context


def session_access(request, session_id, allow_room=False):
    user = identity(request, allow_room=allow_room)
    item = get_document(dbof(request).sesiones, session_id)
    ensure_owner(item, user)
    if user["aud"] == "sala" and user.get("sesion_id") != session_id:
        raise HTTPException(403, "Token de sala de otra sesión")
    peer(request, "usuarios", "GET", f"/internal/usuarios/{user['sub']}/contexto")
    return user, item


def build_app(db=None, peer_override=None):
    app = create_app("sesiones", db, peer_override)
    from sesiones.downloads import router as downloads_router
    app.include_router(downloads_router)

    @app.post("/sesiones", status_code=201)
    def create_session(body: SessionInput, request: Request):
        user, ctx = web_participant(request)
        if any(not value or len(value) > 500 for value in body.actividad.values()):
            raise HTTPException(422, "Actividad inválida")
        if 'duracion_minutos' in body.actividad:
            duration = body.actividad['duracion_minutos']
            if not duration.isdecimal() or not 3 <= int(duration) <= 10:
                raise HTTPException(422, 'La duración debe estar entre 3 y 10 minutos')
        database = dbof(request)
        digest = fingerprint(body.model_dump())
        old = database.sesiones.find_one({"usuario_id": user["sub"], "solicitud_id": body.solicitud_id})
        if old:
            if old["solicitud_hash"] != digest:
                raise HTTPException(409, "La solicitud ya se utilizó con otros datos")
            return clean(old)
        mode = config("modalidades")[body.modalidad]
        evaluation = ctx["evaluacion_tonos"]
        if mode["evaluacion_obligatoria"] and not evaluation:
            raise HTTPException(409, "Completar primero la evaluación de tonos aprobada")
        data = {**body.model_dump(), "usuario_id": user["sub"], "solicitud_hash": digest,
                "perfil_version": ctx["perfil"]["version"], "consentimiento_version": ctx["consentimiento_version"],
                "evaluacion_tonos_id": evaluation["_id"] if mode["evaluacion_obligatoria"] else None,
                "recomendacion_ids": [], "estado": "preparada", "eventos": [], "creado_en": now()}
        database.sesiones.insert_one(data)
        return clean(data)

    @app.get("/sesiones/{session_id}")
    def read_session(session_id: str, request: Request):
        _, item = session_access(request, session_id, allow_room=True)
        return clean({k: v for k, v in item.items() if k not in {"vinculacion", "solicitud_hash"}})

    @app.post("/sesiones/{session_id}/vinculacion")
    def link_code(session_id: str, request: Request):
        _, item = session_access(request, session_id)
        if item["estado"] != "preparada" or item.get("vinculacion", {}).get("canjeado_en"):
            raise HTTPException(409, "Sesión no disponible para vincular")
        code = secrets.token_urlsafe(32)
        result = dbof(request).sesiones.update_one({"_id": item["_id"], "estado": "preparada", "vinculacion.canjeado_en": {"$exists": False}},
            {"$set": {"vinculacion": {"codigo_hash": hashlib.sha256(code.encode()).hexdigest(), "caduca_en": now() + timedelta(minutes=5), "intentos": 0}}})
        if not result.matched_count:
            raise HTTPException(409, "La sala ya fue vinculada")
        return {"codigo": code, "caduca_en_segundos": 300}

    @app.post("/sesiones/{session_id}/canje")
    def exchange(session_id: str, body: Exchange, request: Request):
        database = dbof(request)
        item = get_document(database.sesiones, session_id)
        peer(request, "usuarios", "GET", f"/internal/usuarios/{item['usuario_id']}/contexto")
        link = item.get("vinculacion", {})
        if not link or link.get("canjeado_en") or link.get("intentos", 0) >= 5:
            raise HTTPException(403, "Código no disponible")
        result = database.sesiones.find_one_and_update({"_id": item["_id"], "estado": "preparada",
            "vinculacion.codigo_hash": hashlib.sha256(body.codigo.encode()).hexdigest(),
            "vinculacion.caduca_en": {"$gt": now()}, "vinculacion.canjeado_en": {"$exists": False}, "vinculacion.intentos": {"$lt": 5}},
            {"$set": {"vinculacion.canjeado_en": now()}}, return_document=ReturnDocument.AFTER)
        if not result:
            database.sesiones.update_one({"_id": item["_id"], "vinculacion.canjeado_en": {"$exists": False}}, {"$inc": {"vinculacion.intentos": 1}})
            raise HTTPException(403, "Código incorrecto, vencido o ya canjeado")
        return {"access_token": token(item["usuario_id"], session_id=session_id), "token_type": "bearer", "expires_in": 1800}

    @app.post("/sesiones/{session_id}/estado")
    def state(session_id: str, body: StateInput, request: Request):
        user, item = session_access(request, session_id, allow_room=True)
        if user["aud"] != "sala" and body.estado != "interrumpida":
            raise HTTPException(403, "La actividad de aprendizaje se controla desde la sala vinculada")
        transitions = {"preparada": {"activa", "interrumpida"}, "activa": {"pausada", "finalizada", "interrumpida"},
                       "pausada": {"activa", "finalizada", "interrumpida"}}
        if item["estado"] == body.estado:
            return {"estado": item["estado"]}
        if body.estado not in transitions.get(item["estado"], set()):
            raise HTTPException(409, "Transición no permitida")
        if len(item["eventos"]) >= 500:
            raise HTTPException(409, "Límite de eventos alcanzado")
        fields = {"estado": body.estado}
        if body.estado == "activa" and not item.get("inicio"):
            if not item["recomendacion_ids"]:
                raise HTTPException(409, "Generar la recomendación antes de iniciar")
            ctx = peer(request, "usuarios", "GET", f"/internal/usuarios/{user['sub']}/contexto")
            if ctx["consentimiento_version"] != item["consentimiento_version"]:
                raise HTTPException(409, "Consentimiento modificado; crear una nueva sesión")
            fields["inicio"] = now()
        if body.estado in {"finalizada", "interrumpida"}:
            fields["fin"] = now()
        event = {"evento_id": secrets.token_hex(16), "origen": "sala_virtual" if user["aud"] == "sala" else "web",
                 "tipo": body.estado, "ocurrido_en": now(), "recibido_en": now(), "datos": {}}
        result = dbof(request).sesiones.update_one({"_id": item["_id"], "estado": item["estado"], "eventos.499": {"$exists": False}},
            {"$set": fields, "$push": {"eventos": event}})
        if not result.matched_count:
            raise HTTPException(409, "Sesión modificada; consultar de nuevo")
        return {"estado": body.estado}

    @app.post("/sesiones/{session_id}/eventos")
    def playback_event(session_id: str, body: PlaybackEvent, request: Request):
        _, item = session_access(request, session_id)
        if body.ocurrido_en.tzinfo is None or abs((now() - body.ocurrido_en).total_seconds()) > 86400:
            raise HTTPException(422, "Fecha UTC de evento inválida o fuera de 24 horas")
        payload = body.model_dump()
        digest = fingerprint(payload)
        old = next((x for x in item["eventos"] if x["evento_id"] == body.evento_id), None)
        if old:
            if old.get("solicitud_hash") != digest:
                raise HTTPException(409, "ID de evento reutilizado con otro contenido")
            return {"registrado": True, "duplicado": True}
        if item["estado"] not in {"activa", "pausada"}:
            raise HTTPException(409, "Sesión no activa")
        if body.datos.recomendacion_id not in item["recomendacion_ids"]:
            raise HTTPException(422, "Recomendación ajena a la sesión")
        rec = peer(request, "recomendacion", "GET", f"/internal/recomendaciones/{body.datos.recomendacion_id}")
        matches = [x for x in rec["canciones"] if x["track_id"] == body.datos.track_id and x["audio_id"] == body.datos.audio_id]
        if not matches:
            raise HTTPException(422, "Grabación no recomendada")
        audio = get_document(dbof(request).audios, body.datos.audio_id)
        if body.datos.posicion_ms > audio["duracion_ms"] + 1000:
            raise HTTPException(422, "Posición fuera del audio")
        event = {**payload, "origen": "web", "recibido_en": now(), "solicitud_hash": digest}
        result = dbof(request).sesiones.update_one({"_id": item["_id"], "estado": {"$in": ["activa", "pausada"]},
            "eventos.evento_id": {"$ne": body.evento_id}, "eventos.479": {"$exists": False}}, {"$push": {"eventos": event}})
        # Reservar 20 eventos para cerrar/pausar la actividad.
        if not result.matched_count:
            raise HTTPException(409, "Evento concurrente o límite de eventos alcanzado; consultar sesión")
        return {"registrado": True, "duplicado": False}

    @app.post("/audios", status_code=201)
    def register_audio(body: AudioInput, request: Request):
        _, ctx = web_participant(request)
        if ctx["rol"] != "investigador":
            raise HTTPException(403, "Solo el investigador registra archivos autorizados")
        if (body.tipo == "cancion" and (not body.track_id or body.tono_id)) or (body.tipo == "tono" and (not body.tono_id or body.track_id)):
            raise HTTPException(422, "Indicar solo track_id para canción o tono_id para tono")
        if body.tipo == "tono" and body.tono_id not in {x["tono_id"] for x in config("tonos-v1")["tonos"]}:
            raise HTTPException(422, "Tono no configurado")
        if body.tipo == "cancion":
            peer(request, "recomendacion", "GET", f"/internal/canciones/{body.track_id}")
        path = safe_path(body.ubicacion)
        # Primera versión: WAV PCM permite comprobar duración sin ffmpeg.
        if path.suffix.lower() != ".wav":
            raise HTTPException(422, "Esta versión registra WAV PCM; convertir legalmente el archivo antes de registrarlo")
        try:
            with wave.open(str(path), "rb") as stream:
                duration = round(stream.getnframes() / stream.getframerate() * 1000)
                if duration <= 0 or stream.getnchannels() not in (1, 2):
                    raise ValueError()
        except (wave.Error, ValueError, EOFError):
            raise HTTPException(422, "Audio WAV inválido")
        data = {**body.model_dump(), "formato": "audio/wav", "duracion_ms": duration,
                "hash_archivo": file_hash(path), "disponible": True, "verificado_en": now()}
        dbof(request).audios.insert_one(data)
        return clean(data)

    @app.get("/audios/{audio_id}/contenido")
    def audio_content(audio_id: str, request: Request, sesion_id: str | None = None, evaluacion_id: str | None = None):
        user, _ = web_participant(request)
        audio = get_document(dbof(request).audios, audio_id)
        if audio["tipo"] == "cancion":
            if not sesion_id:
                raise HTTPException(422, "Indicar sesion_id")
            _, session = session_access(request, sesion_id)
            if session["estado"] not in {"preparada", "activa", "pausada"}:
                raise HTTPException(409, "Sesión cerrada")
            allowed = False
            for rec_id in session["recomendacion_ids"]:
                rec = peer(request, "recomendacion", "GET", f"/internal/recomendaciones/{rec_id}")
                allowed |= any(x["audio_id"] == audio_id for x in rec["canciones"])
            if not allowed:
                raise HTTPException(403, "Audio no seleccionado para esta sesión")
        else:
            if not evaluacion_id:
                raise HTTPException(422, "Indicar evaluacion_id")
            evaluation = peer(request, "usuarios", "GET", f"/internal/evaluaciones/{evaluacion_id}")
            ensure_owner(evaluation, user)
            if evaluation["estado"] != "en_curso" or audio_id not in {x["audio_id"] for x in evaluation["audios_utilizados"].values()}:
                raise HTTPException(403, "Audio ajeno a esta evaluación o evaluación cerrada")
        if not available(audio):
            raise HTTPException(409, "Audio no disponible o archivo modificado")
        return FileResponse(safe_path(audio["ubicacion"]), media_type=audio["formato"], filename=None)

    @app.get("/encuestas/configuracion")
    def questionnaire(request: Request):
        web_participant(request)
        return config("cuestionario-v1")

    @app.post("/sesiones/{session_id}/encuesta", status_code=201)
    def survey(session_id: str, body: SurveyInput, request: Request):
        user, session = session_access(request, session_id)
        if session["estado"] not in {"finalizada", "interrumpida"} or not session.get("inicio"):
            raise HTTPException(409, "La actividad debe haberse iniciado y cerrado")
        cfg = config("cuestionario-v1")
        if not cfg["aprobado"]:
            raise HTTPException(503, "Cuestionario pendiente de aprobación")
        if body.cuestionario_version != cfg["version"]:
            raise HTTPException(409, "Versión de cuestionario distinta")
        definitions = {x["pregunta_id"]: x for x in cfg["preguntas"]}
        ids = [x.pregunta_id for x in body.respuestas]
        if len(ids) != len(set(ids)) or set(ids) != set(definitions):
            raise HTTPException(422, "Respuestas incompletas o duplicadas")
        for answer in body.respuestas:
            definition = definitions[answer.pregunta_id]
            if not definition["min"] <= answer.valor <= definition["max"]:
                raise HTTPException(422, "Respuesta fuera de escala")
        old = dbof(request).encuestas.find_one({"sesion_id": session_id})
        payload = body.model_dump()
        if old:
            if old["respuestas"] != payload["respuestas"]:
                raise HTTPException(409, "La encuesta ya fue respondida")
            return clean(old)
        data = {**payload, "sesion_id": session_id, "usuario_id": user["sub"],
                "cuestionario_utilizado": cfg, "respondido_en": now()}
        dbof(request).encuestas.insert_one(data)
        return clean(data)

    @app.get("/investigacion/exportacion")
    def export(request: Request, limite: int = 100, despues_de: str | None = None):
        _, ctx = web_participant(request)
        if ctx["rol"] != "investigador":
            raise HTTPException(403, "Solo investigador")
        if not 1 <= limite <= 500:
            raise HTTPException(422, "Límite entre 1 y 500")
        query = {"_id": {"$gt": oid(despues_de)}} if despues_de else {}
        sessions = list(dbof(request).sesiones.find(query, {"vinculacion": 0, "solicitud_hash": 0}).sort("_id", 1).limit(limite))
        rows = []
        for session in sessions:
            sid = str(session["_id"])
            recs = peer(request, "recomendacion", "GET", f"/internal/sesiones/{sid}/exportacion")
            rows.append({"sesion": session, "encuesta": dbof(request).encuestas.find_one({"sesion_id": sid}), **recs})
        return clean({"datos_seudonimizados": True, "registros": rows, "siguiente": str(sessions[-1]["_id"]) if len(sessions) == limite else None})

    @app.get("/internal/sesiones/{session_id}")
    def internal_session(session_id: str, request: Request):
        internal(request, {"recomendacion"})
        item = get_document(dbof(request).sesiones, session_id)
        return clean({k: v for k, v in item.items() if k not in {"vinculacion", "eventos", "solicitud_hash"}})

    @app.post("/internal/sesiones/{session_id}/recomendaciones")
    def recommendation_link(session_id: str, body: LinkInput, request: Request):
        internal(request, {"recomendacion"})
        oid(body.recomendacion_id)
        item = get_document(dbof(request).sesiones, session_id)
        if body.recomendacion_id in item["recomendacion_ids"]:
            return {"vinculada": True}
        result = dbof(request).sesiones.update_one({"_id": item["_id"], "estado": "preparada", "recomendacion_ids.9": {"$exists": False}},
            {"$addToSet": {"recomendacion_ids": body.recomendacion_id}})
        if not result.matched_count:
            raise HTTPException(409, "Sesión no preparada o límite de recomendaciones alcanzado")
        return {"vinculada": True}

    def audio_map(request, field, values):
        found = {}
        for audio in dbof(request).audios.find({field: {"$in": values}}).sort("_id", -1):
            key = audio[field]
            valid = available(audio)
            dbof(request).audios.update_one({"_id": audio["_id"]}, {"$set": {"disponible": valid, "verificado_en": now()}})
            if key not in found and valid:
                found[key] = {"audio_id": str(audio["_id"]), "duracion_ms": audio["duracion_ms"]}
        return found

    @app.post("/internal/audios/disponibles")
    def audios(body: TrackIds, request: Request):
        internal(request, {"recomendacion"})
        return audio_map(request, "track_id", body.track_ids)

    @app.post("/internal/audios/tonos")
    def tones(body: ToneIds, request: Request):
        internal(request, {"usuarios"})
        return audio_map(request, "tono_id", body.tono_ids)
    return app


app = build_app()
