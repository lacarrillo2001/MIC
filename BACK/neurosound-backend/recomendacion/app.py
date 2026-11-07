from typing import Literal
import re

from fastapi import HTTPException, Request
from pydantic import Field

from recomendacion.engine import musical_id, rank
from shared.genres import profile_genres, resolve_genres, suggestions
from shared.runtime import (Model, clean, config, create_app, dbof, ensure_owner, fingerprint,
                            get_document, identity, internal, now, peer)


class RecommendationInput(Model):
    solicitud_id: str = Field(min_length=8, max_length=100)
    sesion_id: str


class FeedbackInput(Model):
    solicitud_id: str = Field(min_length=8, max_length=100)
    recomendacion_id: str
    track_id: str = Field(min_length=1, max_length=100)
    preferencia: Literal["me_gusta", "no_me_gusta", "neutral"] | None = None
    molestia: bool | None = None


class ArtistIds(Model):
    ids: list[str] = Field(max_length=50)


class GenreNames(Model):
    generos: list[str] = Field(max_length=50)


def context(request, user):
    return peer(request, "usuarios", "GET", f"/internal/usuarios/{user['sub']}/contexto")


def song_by_id(database, track_id):
    item = database.songsV2.find_one({"$or": [{"id": track_id}, {"idros": track_id}]})
    if not item:
        raise HTTPException(404, "Canción no encontrada")
    return item


def apply_feedback(request, item):
    if item.get('tipo') in {'youtube_web', 'voz_web'}:
        raise HTTPException(409, 'El feedback web no admite ajustes de sesiones VR')
    if item["estado_ajuste"] in {"aplicado", "sin_cambio"}:
        return clean(item)
    database = dbof(request)
    rules = item["reglas_utilizadas"]
    for _ in range(3):
        ctx = peer(request, "usuarios", "GET", f"/internal/usuarios/{item['usuario_id']}/contexto")
        profile = ctx["perfil"]
        targets = {}
        for key in ("energy", "valence"):
            value = item["atributos_utilizados"].get(key)
            if value is None:
                continue
            previous = profile["afinidad_aprendida"].get(key)
            targets[key] = value if previous is None else previous + rules["learning_rate"] * (value - previous)
        if not targets:
            database.feedback.update_one({"_id": item["_id"]}, {"$set": {"estado_ajuste": "sin_cambio"}})
            break
        try:
            result = peer(request, "usuarios", "POST", f"/internal/perfiles/{item['usuario_id']}/ajustes", {
                "feedback_id": str(item["_id"]), "version_esperada": profile["version"], "atributos": targets})
            database.feedback.update_one({"_id": item["_id"]}, {"$set": {
                "estado_ajuste": "aplicado",
                "perfil_version_resultante": None if result["duplicado"] else result["version"],
                "perfil_version_observada": result["version"]}})
            break
        except HTTPException as exc:
            if exc.status_code == 409:
                continue
            # El registro persiste para reenviar la misma solicitud sin duplicar.
            raise
    return clean(database.feedback.find_one({"_id": item["_id"]}))


def build_app(db=None, peer_override=None):
    app = create_app("recomendacion", db, peer_override)
    from recomendacion.youtube_api import router as youtube_router
    app.include_router(youtube_router)

    @app.get("/catalogo/canciones")
    def catalogue(request: Request, pagina: int = 1, limite: int = 30):
        context(request, identity(request))
        if pagina < 1 or pagina > 10000 or not 1 <= limite <= 100:
            raise HTTPException(422, "Paginación inválida")
        songs = list(dbof(request).songsV2.find().sort("_id", 1).skip((pagina - 1) * limite).limit(limite))
        return clean({"pagina": pagina, "canciones": [{**x, "track_id": musical_id(x)} for x in songs]})

    @app.get("/catalogo/artistas")
    def artists(request: Request, pagina: int = 1, limite: int = 30, q: str = '', ids: str = ''):
        context(request, identity(request))
        if pagina < 1 or not 1 <= limite <= 100:
            raise HTTPException(422, "Paginación inválida")
        if len(q) > 100:
            raise HTTPException(422, 'Búsqueda demasiado larga')
        query = {'name': {'$regex': re.escape(q.strip()), '$options': 'i'}} if q.strip() else {}
        if ids:
            requested = ids.split(',')
            if len(requested) > 50 or any(not x or len(x) > 100 for x in requested):
                raise HTTPException(422, 'Identificadores de artistas inválidos')
            query = {'$and': [query, {'id': {'$in': requested}}]}
        return clean(list(dbof(request).artists.find(query).sort("_id", 1).skip((pagina - 1) * limite).limit(limite)))

    @app.get('/catalogo/generos')
    def genres(request: Request, q: str = ''):
        context(request, identity(request))
        if len(q) > 100:
            raise HTTPException(422, 'Búsqueda demasiado larga')
        return suggestions(dbof(request), q)

    @app.post("/recomendaciones", status_code=201)
    def recommend(body: RecommendationInput, request: Request):
        user = identity(request)
        ctx = context(request, user)
        database = dbof(request)
        digest = fingerprint(body.model_dump())
        old = database.recomendaciones.find_one({"usuario_id": user["sub"], "solicitud_id": body.solicitud_id})
        if old:
            if old.get("tipo") == "youtube_web":
                raise HTTPException(409, "Solicitud utilizada para una lista web, no para una sesión VR")
            if old["solicitud_hash"] != digest:
                raise HTTPException(409, "La solicitud ya se utilizó con otros datos")
            peer(request, "sesiones", "POST", f"/internal/sesiones/{old['sesion_id']}/recomendaciones", {"recomendacion_id": str(old["_id"])})
            database.recomendaciones.update_one({"_id": old["_id"]}, {"$set": {"estado_vinculacion": "vinculada"}})
            return clean(database.recomendaciones.find_one({"_id": old["_id"]}))
        session = peer(request, "sesiones", "GET", f"/internal/sesiones/{body.sesion_id}")
        ensure_owner(session, user)
        if session["estado"] != "preparada":
            raise HTTPException(409, "Solo se recomienda antes de iniciar la actividad")
        profile, genre_resolution = profile_genres(database, ctx["perfil"])
        # Evita utilizar el perfil actualizado por feedback dentro de una sesión fijada.
        if profile["version"] != session["perfil_version"]:
            raise HTTPException(409, "Perfil modificado desde la creación; crear nueva sesión")
        mode = config("modalidades")[session["modalidad"]]
        evaluation = None
        if mode["heuristica_frecuencial_activa"]:
            evaluation = peer(request, "usuarios", "GET", f"/internal/evaluaciones/{session['evaluacion_tonos_id']}")
            if evaluation["usuario_id"] != user["sub"] or evaluation["estado"] != "completada" or not evaluation["configuracion_utilizada"]["aprobado"]:
                raise HTTPException(409, "Evaluación no apta para la heurística")
        rules = config("reglas-v1")
        preferred = profile["artistas_preferidos"]
        genre_artists = list(database.artists.find({"genres": {"$in": profile["generos_preferidos"]}}, {"id": 1}).limit(1000))
        preferred_ids = sorted(set(preferred + [x["id"] for x in genre_artists if x.get("id")]))
        # Primero candidatos afines; después completar de modo determinista.
        songs = list(database.songsV2.find({"id_artists": {"$in": preferred_ids}}).sort("_id", 1).limit(rules["candidate_limit"])) if preferred_ids else []
        seen = {str(x["_id"]) for x in songs}
        remaining = rules["candidate_limit"] - len(songs)
        if remaining:
            for item in database.songsV2.find({"_id": {"$nin": [x["_id"] for x in songs]}}).sort("_id", 1).limit(remaining):
                if str(item["_id"]) not in seen:
                    songs.append(item)
        songs = [x for x in songs if isinstance(musical_id(x), str) and musical_id(x)]
        audios = peer(request, "sesiones", "POST", "/internal/audios/disponibles", {"track_ids": sorted(set(musical_id(x) for x in songs))})
        artist_ids = {artist for song in songs for artist in song.get("id_artists", [])}
        genres = {x["id"]: {g.lower() for g in x.get("genres", [])} for x in database.artists.find({"id": {"$in": list(artist_ids)}}) if x.get("id")}
        ranked, track_seen = [], set()
        for song in songs:
            track_id = musical_id(song)
            if track_id not in audios or track_id in track_seen:
                continue
            track_seen.add(track_id)
            song_genres = set().union(*(genres.get(a, set()) for a in song.get("id_artists", [])))
            result = rank(song, profile, song_genres, rules, evaluation)
            ranked.append({**result, "audio_id": audios[track_id]["audio_id"]})
        ranked.sort(key=lambda x: (-x["puntaje_compatibilidad"], x["track_id"]))
        selected = [{**x, "posicion": index + 1} for index, x in enumerate(ranked[:rules["result_limit"]])]
        if not selected:
            raise HTTPException(409, "Sin canciones con archivo disponible y autorizado dentro de la ventana de candidatos")
        data = {**body.model_dump(), "solicitud_hash": digest, "usuario_id": user["sub"], "perfil_utilizado": profile,
                "evaluacion_tonos_utilizada": evaluation, "reglas_version": rules["version"], "reglas_utilizadas": rules,
                "heuristica_frecuencial_activa": mode["heuristica_frecuencial_activa"], "canciones": selected,
                'normalizacion_generos': genre_resolution,
                "candidatos_considerados": len(songs), "estado_vinculacion": "pendiente", "creado_en": now()}
        database.recomendaciones.insert_one(data)
        peer(request, "sesiones", "POST", f"/internal/sesiones/{body.sesion_id}/recomendaciones", {"recomendacion_id": str(data["_id"])})
        database.recomendaciones.update_one({"_id": data["_id"]}, {"$set": {"estado_vinculacion": "vinculada"}})
        data["estado_vinculacion"] = "vinculada"
        return clean(data)

    @app.get("/recomendaciones/{recommendation_id}")
    def read_recommendation(recommendation_id: str, request: Request):
        user = identity(request)
        context(request, user)
        item = get_document(dbof(request).recomendaciones, recommendation_id)
        ensure_owner(item, user)
        return clean(item)

    @app.post("/feedback", status_code=201)
    def feedback(body: FeedbackInput, request: Request):
        user = identity(request)
        context(request, user)
        database = dbof(request)
        digest = fingerprint(body.model_dump())
        old = database.feedback.find_one({"usuario_id": user["sub"], "solicitud_id": body.solicitud_id})
        if old:
            if old["solicitud_hash"] != digest:
                raise HTTPException(409, "La solicitud ya se utilizó con otros datos")
            return apply_feedback(request, old)
        rec = get_document(database.recomendaciones, body.recomendacion_id)
        ensure_owner(rec, user)
        if rec["estado_vinculacion"] != "vinculada":
            raise HTTPException(409, "Recomendación no vinculada")
        song = next((x for x in rec["canciones"] if x["track_id"] == body.track_id), None)
        if not song:
            raise HTTPException(422, "Canción no recomendada")
        if body.preferencia is None and body.molestia is None:
            raise HTTPException(422, "Declarar gusto o molestia")
        session = peer(request, "sesiones", "GET", f"/internal/sesiones/{rec['sesion_id']}")
        if session["estado"] == "preparada":
            raise HTTPException(409, "El feedback requiere actividad iniciada")
        data = {**body.model_dump(), "solicitud_hash": digest, "usuario_id": user["sub"], "sesion_id": rec["sesion_id"],
                "atributos_utilizados": song["atributos_utilizados"], "reglas_version": rec["reglas_version"],
                "reglas_utilizadas": rec["reglas_utilizadas"], "creado_en": now(),
                "estado_ajuste": "pendiente" if body.preferencia == "me_gusta" and body.molestia is not True else "sin_cambio"}
        database.feedback.insert_one(data)
        return apply_feedback(request, data)

    @app.post("/feedback/{feedback_id}/reintentar")
    def retry(feedback_id: str, request: Request):
        user = identity(request)
        context(request, user)
        item = get_document(dbof(request).feedback, feedback_id)
        ensure_owner(item, user)
        if item.get('tipo') in {'youtube_web', 'voz_web'}:
            raise HTTPException(409, 'El feedback web se calcula desde las respuestas vigentes; no admite ajustes VR')
        return apply_feedback(request, item)

    @app.get("/internal/canciones/{track_id}")
    def internal_song(track_id: str, request: Request):
        internal(request, {"sesiones"})
        return {"track_id": musical_id(song_by_id(dbof(request), track_id))}

    @app.post("/internal/artistas/validar")
    def validate_artists(body: ArtistIds, request: Request):
        internal(request, {"usuarios"})
        found = {x["id"] for x in dbof(request).artists.find({"id": {"$in": body.ids}}, {"id": 1})}
        if found != set(body.ids):
            raise HTTPException(422, "Artistas no encontrados en el catálogo")
        return {"validos": True}

    @app.post('/internal/generos/resolver')
    def genres_resolve(body: GenreNames, request: Request):
        internal(request, {'usuarios'})
        if any(not g.strip() or len(g) > 100 for g in body.generos):
            raise HTTPException(422, 'Géneros inválidos')
        return resolve_genres(dbof(request), body.generos)

    @app.get("/internal/recomendaciones/{recommendation_id}")
    def internal_recommendation(recommendation_id: str, request: Request):
        internal(request, {"sesiones"})
        return clean(get_document(dbof(request).recomendaciones, recommendation_id))

    @app.get("/internal/sesiones/{session_id}/exportacion")
    def export(session_id: str, request: Request):
        internal(request, {"sesiones"})
        return clean({"recomendaciones": list(dbof(request).recomendaciones.find({"sesion_id": session_id}, {"solicitud_hash": 0})),
                      "feedback": list(dbof(request).feedback.find({"sesion_id": session_id}, {"solicitud_hash": 0}))})
    return app


app = build_app()
