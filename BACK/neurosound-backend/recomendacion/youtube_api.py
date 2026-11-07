from fastapi import APIRouter, HTTPException, Request
from typing import Literal
from pymongo.errors import DuplicateKeyError
from pydantic import Field
from datetime import timedelta

from recomendacion.engine import musical_id
from recomendacion.questionnaire import rank_questionnaire, session_profile
from recomendacion.youtube import configured, daily_limit, resolve_video
from recomendacion.selection import candidates, diverse, web_profile
from recomendacion.voice import voice_eligibility, voice_label
from shared.genres import profile_genres
from shared.runtime import (Model, clean, config, dbof, ensure_owner, fingerprint, get_document, identity, now, peer)

router = APIRouter(prefix="/youtube", tags=["YouTube web"])


class WebList(Model):
    solicitud_id: str = Field(min_length=8, max_length=100)
    limite: int = Field(default=5, ge=1, le=10)
    modo: Literal['youtube', 'audio'] = 'youtube'
    actividad: Literal['lectura_comprensiva', 'atencion_flechas'] | None = None
    energia_sesion: Literal['suave', 'energica', 'mantener'] = 'mantener'
    duracion_minutos: int = Field(default=5, ge=3, le=10)


class ResolveInput(Model):
    track_id: str = Field(min_length=1, max_length=100)


class WebFeedback(ResolveInput):
    respuesta: Literal['me_gusta', 'no_me_gusta', 'molestia', 'neutral']
    revision: int = Field(default=0, ge=0)


class VoiceReport(ResolveInput):
    tiene_voz: bool
    revision: int = Field(default=0, ge=0)


def user_context(request):
    user = identity(request)
    context = peer(request, "usuarios", "GET", f"/internal/usuarios/{user['sub']}/contexto")
    return user, context


@router.get("/configuracion")
def configuration(request: Request):
    user_context(request)
    return {"configurado": configured(), "max_busquedas_dia_local": daily_limit(), "solo_web_visible": True,
            "coincidencia_acustica_verificada": False, "cache_dias": 7}


@router.get('/feedback')
def feedback_history(request: Request, pagina: int = 1):
    user, _ = user_context(request)
    if not 1 <= pagina <= 10000:
        raise HTTPException(422, 'Página inválida')
    items = dbof(request).feedback.find({'usuario_id': user['sub'], 'tipo': 'youtube_web'})
    return clean(list(items.sort('actualizado_en', -1).skip((pagina - 1) * 20).limit(20)))


@router.get('/voz')
def voice_history(request: Request, pagina: int = 1):
    user, _ = user_context(request)
    if not 1 <= pagina <= 10000:
        raise HTTPException(422, 'Página inválida')
    items = dbof(request).feedback.find({'usuario_id': user['sub'], 'tipo': 'voz_web'})
    return clean(list(items.sort('actualizado_en', -1).skip((pagina - 1) * 20).limit(20)))


@router.post("/recomendaciones", status_code=201)
def web_recommendations(body: WebList, request: Request):
    user, ctx = user_context(request)
    if body.modo == 'youtube' and not configured():
        raise HTTPException(503, "Configurar YOUTUBE_API_KEY en el backend para activar búsquedas automáticas")
    db = dbof(request)
    digest = fingerprint(body.model_dump())
    old = db.recomendaciones.find_one({"usuario_id": user["sub"], "solicitud_id": body.solicitud_id})
    if old:
        if old.get("tipo") != "youtube_web" or old["solicitud_hash"] != digest:
            raise HTTPException(409, "Solicitud utilizada para otra operación")
        return clean(old)
    rules = config("reglas-v1")
    normalized_profile, genre_resolution = profile_genres(db, ctx['perfil'])
    profile, excluded = web_profile(db, user['sub'], normalized_profile, rules['learning_rate'])
    questionnaire_rules = config('recomendacion-web-v3')
    profile = session_profile(profile, body.energia_sesion, questionnaire_rules)
    voice_reports = list(db.feedback.find({'usuario_id': user['sub'], 'tipo': 'voz_web', 'tiene_voz': True}))
    reported = [item['track_id'] for item in voice_reports]
    eligibility = voice_eligibility(profile.get('preferencia_voz'), questionnaire_rules['voice_prefilter'], reported)
    songs = candidates(db, profile, rules, excluded, eligibility=eligibility)
    artist_ids = {a for song in songs for a in song.get("id_artists", [])}
    genres = {x["id"]: set(g.lower() for g in x.get("genres", [])) for x in db.artists.find({"id": {"$in": list(artist_ids)}}) if x.get("id")}
    ranked, seen = [], set()
    for song in songs:
        tid = musical_id(song)
        if not isinstance(tid, str) or not tid or tid in seen or tid in excluded:
            continue
        seen.add(tid)
        associated = set().union(*(genres.get(a, set()) for a in song.get("id_artists", [])))
        duration = song.get('duration_ms')
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 15000 <= duration <= 1200000:
            continue
        row = {**rank_questionnaire(song, profile, associated, questionnaire_rules), "duration_ms": duration, 'id_artists': song.get('id_artists', [])}
        row['clasificacion_voz'] = voice_label(row, reported, questionnaire_rules['voice_prefilter'])
        ranked.append(row)
    previous = list(db.recomendaciones.find({'usuario_id': user['sub'], 'tipo': 'youtube_web',
                    'reproducidas.0': {'$exists': True}}).sort('ultima_reproduccion_en', -1).limit(2))
    recent = {tid for rec in previous for tid in rec.get('reproducidas', [])}
    selected = [{**x, "posicion": i + 1} for i, x in enumerate(diverse(ranked, body.limite, body.solicitud_id, recent))]
    if not selected:
        raise HTTPException(409, "No encontramos candidatas con estas preferencias. Puedes cambiar la preferencia de voz; no se incluyeron canciones fuera del filtro.")
    item = {"tipo": "youtube_web", 'modo_reproduccion': body.modo, "solicitud_id": body.solicitud_id, "solicitud_hash": digest,
            "usuario_id": user["sub"], "sesion_id": None, "estado_vinculacion": "solo_web", "perfil_utilizado": profile,
            "reglas_version": questionnaire_rules["version"], "reglas_utilizadas": questionnaire_rules, "canciones": selected,
            'contexto_sesion': {'actividad': body.actividad, 'energia_sesion': body.energia_sesion, 'duracion_minutos': body.duracion_minutos},
            'preseleccion_voz': {'preferencia': profile.get('preferencia_voz'), 'umbrales': questionnaire_rules['voice_prefilter'],
                                'verificacion_audio': False, 'correcciones_personales': len(reported)},
            'aviso_seleccion': 'Se encontraron menos canciones que las solicitadas; no se relajó el filtro de voz.' if len(selected) < body.limite else None,
            'seleccion_version': 'candidatos-diversidad-web-v2', 'candidatos_considerados': len(songs),
            'normalizacion_generos': genre_resolution,
            'diversidad': {'max_artista': 2, 'listas_recientes': 2, 'banda_puntos': 5, 'relajar_si_insuficiente': True},
            'reproducidas': [],
            "creado_en": now(), "advertencia": "Prueba web independiente, no sesión de investigación VR"}
    try:
        db.recomendaciones.insert_one(item)
    except DuplicateKeyError:
        old = db.recomendaciones.find_one({'usuario_id': user['sub'], 'solicitud_id': body.solicitud_id})
        if not old or old.get('tipo') != 'youtube_web' or old.get('solicitud_hash') != digest:
            raise HTTPException(409, 'Solicitud utilizada para otra operación')
        return clean(old)
    return clean(item)


@router.post("/recomendaciones/{recommendation_id}/resolver")
def resolve(recommendation_id: str, body: ResolveInput, request: Request):
    user, _ = user_context(request)
    db = dbof(request)
    rec = get_document(db.recomendaciones, recommendation_id)
    ensure_owner(rec, user)
    if rec.get("tipo") != "youtube_web":
        raise HTTPException(409, "La reproducción YouTube automática solo está habilitada para listas web visibles")
    song = next((x for x in rec["canciones"] if x["track_id"] == body.track_id), None)
    if not song:
        raise HTTPException(422, "Canción no incluida en esta recomendación")
    result = resolve_video(db, song, client=getattr(request.app.state, "youtube_http", None))
    feedback = db.feedback.find_one(feedback_key(user['sub'], body.track_id))
    return {**result, 'respuesta_actual': feedback.get('respuesta', 'neutral') if feedback else 'neutral',
            'revision_feedback': feedback.get('revision', 0) if feedback else 0}


def feedback_key(uid, track_id):
    return {'usuario_id': uid, 'solicitud_id': 'youtube-feedback:' + fingerprint(track_id)}


def owned_song(request, recommendation_id, track_id):
    user, _ = user_context(request)
    db = dbof(request)
    rec = get_document(db.recomendaciones, recommendation_id)
    ensure_owner(rec, user)
    if rec.get('tipo') != 'youtube_web':
        raise HTTPException(409, 'Esta operación solo admite listas web')
    song = next((x for x in rec['canciones'] if x['track_id'] == track_id), None)
    if song is None:
        raise HTTPException(422, 'Canción no incluida en esta lista')
    return user, db, rec, song


@router.post('/recomendaciones/{recommendation_id}/reproduccion')
def playback(recommendation_id: str, body: ResolveInput, request: Request):
    user, db, rec, song = owned_song(request, recommendation_id, body.track_id)
    started = rec.get('inicio_web')
    duration = rec.get('contexto_sesion', {}).get('duracion_minutos', 5)
    if started and now() >= started + timedelta(minutes=duration):
        raise HTTPException(409, 'La sesión alcanzó su duración; prepara otra sesión')
    db.recomendaciones.update_one({'_id': rec['_id'], 'inicio_web': {'$exists': False}}, {'$set': {'inicio_web': now()}})
    # Evento declarado por el reproductor PLAYING; no acredita escucha completa ni atención.
    db.recomendaciones.update_one({'_id': rec['_id'], 'reproducidas': {'$ne': body.track_id}},
        {'$addToSet': {'reproducidas': body.track_id}, '$set': {'ultima_reproduccion_en': now()}})
    current = db.recomendaciones.find_one({'_id': rec['_id']})
    return {'registrada': True, 'track_id': body.track_id, 'inicio_web': current['inicio_web'], 'duracion_minutos': duration}


@router.post('/recomendaciones/{recommendation_id}/feedback')
def web_feedback(recommendation_id: str, body: WebFeedback, request: Request):
    user, db, rec, song = owned_song(request, recommendation_id, body.track_id)
    if body.track_id not in rec.get('reproducidas', []):
        raise HTTPException(409, 'Reproduce la canción antes de valorarla')
    key = feedback_key(user['sub'], body.track_id)
    digest = fingerprint(body.model_dump())
    old = db.feedback.find_one(key)
    if old and old.get('solicitud_hash') == digest:
        return clean(old)
    if (old or {}).get('revision', 0) != body.revision:
        raise HTTPException(409, 'La respuesta cambió en otra pestaña; vuelve a cargar la canción')
    data = {**key, 'tipo': 'youtube_web', 'track_id': body.track_id, 'recomendacion_id': recommendation_id,
            'sesion_id': None, 'respuesta': body.respuesta, 'revision': body.revision + 1,
            'name': song.get('name'), 'artists': song.get('artists', []),
            'solicitud_hash': digest, 'atributos_utilizados': song['atributos_utilizados'],
            'creado_en': old['creado_en'] if old else now(), 'actualizado_en': now(),
            'estado_ajuste': 'derivado_para_proximas_listas'}
    if old:
        if not db.feedback.update_one({**key, 'revision': body.revision}, {'$set': data}).matched_count:
            raise HTTPException(409, 'Respuesta modificada simultáneamente')
    else:
        try:
            db.feedback.insert_one(data)
        except DuplicateKeyError:
            current = db.feedback.find_one(key)
            if current.get('solicitud_hash') == digest:
                return clean(current)
            raise HTTPException(409, 'Respuesta creada simultáneamente; recarga la canción')
    return clean(db.feedback.find_one(key))


@router.get('/recomendaciones/{recommendation_id}/feedback')
def current_web_feedback(recommendation_id: str, track_id: str, request: Request):
    user, db, _, _ = owned_song(request, recommendation_id, track_id)
    item = db.feedback.find_one(feedback_key(user['sub'], track_id))
    return {'respuesta_actual': item['respuesta'] if item else 'neutral', 'revision_feedback': item['revision'] if item else 0}


def voice_key(uid, tid):
    return {'usuario_id': uid, 'solicitud_id': 'voice-report:' + fingerprint(tid)}


@router.get('/recomendaciones/{recommendation_id}/voz')
def current_voice(recommendation_id: str, track_id: str, request: Request):
    user, db, _, _ = owned_song(request, recommendation_id, track_id)
    item = db.feedback.find_one(voice_key(user['sub'], track_id))
    return {'tiene_voz': item.get('tiene_voz', False) if item else False,
            'revision': item.get('revision', 0) if item else 0}


@router.post('/recomendaciones/{recommendation_id}/voz')
def report_voice(recommendation_id: str, body: VoiceReport, request: Request):
    user, db, rec, song = owned_song(request, recommendation_id, body.track_id)
    if body.track_id not in rec.get('reproducidas', []):
        raise HTTPException(409, 'Reproduce la canción antes de informar que tiene voz')
    key = voice_key(user['sub'], body.track_id)
    old = db.feedback.find_one(key)
    digest = fingerprint(body.model_dump())
    if old and old.get('solicitud_hash') == digest:
        return clean(old)
    if (old or {}).get('revision', 0) != body.revision:
        raise HTTPException(409, 'La corrección cambió en otra pestaña; vuelve a seleccionar la canción')
    data = {**key, 'tipo': 'voz_web', 'track_id': body.track_id, 'tiene_voz': body.tiene_voz,
            'revision': body.revision + 1, 'solicitud_hash': digest,
            'recomendacion_id': recommendation_id, 'name': song.get('name'), 'artists': song.get('artists', []),
            'metodo': 'reporte_usuario', 'letra_verificada': False,
            'creado_en': old['creado_en'] if old else now(), 'actualizado_en': now()}
    if old:
        if not db.feedback.update_one({**key, 'revision': body.revision}, {'$set': data}).matched_count:
            raise HTTPException(409, 'Corrección modificada simultáneamente')
    else:
        try:
            db.feedback.insert_one(data)
        except DuplicateKeyError:
            current = db.feedback.find_one(key)
            if current.get('solicitud_hash') == digest:
                return clean(current)
            raise HTTPException(409, 'Corrección creada simultáneamente; vuelve a seleccionar la canción')
    return clean(db.feedback.find_one(key))
