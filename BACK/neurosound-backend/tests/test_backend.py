import copy
import io
import wave
from datetime import timedelta

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError, OperationFailure

import sesiones.app as sessions_module
import usuarios.app as users_module
from recomendacion.engine import frequency_category, rank
from shared.runtime import COLLECTIONS, config, initialize, now, token


def prepare(system, student):
    clients, db, path = system
    headers, user_id = student
    db.artists.insert_one({"id": "artist1", "name": "Synthetic artist", "genres": ["piano"]})
    db.songsV2.insert_one({"idros": "track1", "name": "Synthetic track", "artists": ["Synthetic artist"],
                          "id_artists": ["artist1"], "energy": 0.0, "valence": 0.3, "tempo": 80,
                          "acousticness": .9, "danceability": .2, "instrumentalness": .99, "loudness": -12})
    with wave.open(str(path / "test.wav"), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * 8000)
    db.usuarios.update_one({"_id": ObjectId(user_id)}, {"$set": {"rol": "investigador"}})
    audio = clients["sesiones"].post("/audios", headers=headers, json={"tipo": "cancion", "track_id": "track1",
        "ubicacion": "test.wav", "correspondencia_verificada": True, "fuente_autorizada": True})
    assert audio.status_code == 201, audio.text
    profile = clients["usuarios"].put("/perfiles/me", headers=headers, json={"version_esperada": 1,
        "artistas_preferidos": ["artist1"], "generos_preferidos": ["piano"], "tempo_preferido": "lento"})
    assert profile.status_code == 200, profile.text
    session = clients["sesiones"].post("/sesiones", headers=headers, json={"solicitud_id": "session-0001", "actividad": {"id": "lectura", "version": "piloto"}})
    assert session.status_code == 201, session.text
    sid = session.json()["_id"]
    rec = clients["recomendacion"].post("/recomendaciones", headers=headers, json={"solicitud_id": "recommend-0001", "sesion_id": sid})
    assert rec.status_code == 201, rec.text
    return sid, rec.json(), audio.json()


def activate(system, student, sid):
    client = system[0]["sesiones"]
    headers, _ = student
    result = client.post(f"/sesiones/{sid}/vinculacion", headers=headers)
    assert result.status_code == 200, result.text
    code = result.json()["codigo"]
    result = client.post(f"/sesiones/{sid}/canje", json={"codigo": code})
    assert result.status_code == 200, result.text
    room_headers = {"Authorization": "Bearer " + result.json()["access_token"]}
    result = client.post(f"/sesiones/{sid}/estado", headers=room_headers, json={"estado": "activa"})
    assert result.status_code == 200, result.text
    return room_headers, code


def test_collections_indexes_startup_and_preservation(system):
    clients, db, _ = system
    assert set(db.list_collection_names()) == {x for group in COLLECTIONS.values() for x in group}
    marker = db.songsV2.insert_one({"id": "preserve", "unknown_field": {"data": [1, 2]}}).inserted_id
    for service in COLLECTIONS:
        initialize(db, service)
        initialize(db, service)
    assert db.songsV2.find_one({"_id": marker})["unknown_field"] == {"data": [1, 2]}
    db.perfiles.insert_one({"usuario_id": ObjectId("123456789012345678901234")})
    with pytest.raises(DuplicateKeyError):
        db.perfiles.insert_one({"usuario_id": ObjectId("123456789012345678901234")})
    for client in clients.values():
        assert client.get("/health/ready").status_code == 200


def test_startup_fails_on_index_error(system, monkeypatch):
    db = system[1]
    monkeypatch.setattr(users_module, "initialize", None, raising=False)
    def fail(*args, **kwargs):
        raise OperationFailure("index conflict", code=85)
    monkeypatch.setattr(type(db.perfiles), "create_index", fail)
    with pytest.raises(OperationFailure):
        with TestClient(users_module.build_app(db)):
            pass


def test_auth_age_consent_authorization(system, student):
    clients, db, _ = system
    headers, uid = student
    assert clients["usuarios"].get("/usuarios/me").status_code == 401
    assert "password_hash" not in clients["usuarios"].get("/usuarios/me", headers=headers).json()
    assert db.usuarios.find_one({"_id": ObjectId(uid)})["password_hash"] != "long-password-12345"
    assert clients["usuarios"].post("/auth/registro", json={"email": "minor@example.test", "password": "long-password-12345", "mayor_edad_confirmado": False,
        "consentimiento_aceptado": True, "consentimiento_version": "consentimiento-v1"}).status_code == 422
    assert clients["usuarios"].get(f"/internal/usuarios/{uid}/contexto", headers=headers).status_code == 403
    assert clients["usuarios"].post("/auth/login", json={"email": "student@example.test", "password": "wrong"}).status_code == 401
    clients["usuarios"].post("/usuarios/me/retiro", headers=headers)
    assert clients["sesiones"].post("/sesiones", headers=headers, json={"solicitud_id": "session-0001", "actividad": {"id": "test"}}).status_code == 403


def test_draft_protocols_blocked(system, student):
    clients, _, _ = system
    headers, _ = student
    assert clients["usuarios"].post("/evaluaciones-tonos", headers=headers).status_code == 503
    assert not clients["sesiones"].get("/encuestas/configuracion", headers=headers).json()["aprobado"]
    assert clients["sesiones"].post("/sesiones", headers=headers, json={"solicitud_id": "heuristic-0001", "actividad": {"id": "test"}, "modalidad": "personalizada_heuristica"}).status_code == 409


def test_full_flow_feedback_idempotency_events_and_audio(system, student, monkeypatch):
    clients, db, path = system
    headers, uid = student
    sid, rec, audio = prepare(system, student)
    assert rec["canciones"][0]["track_id"] == "track1"
    assert rec["canciones"][0]["atributos_utilizados"]["energy"] == 0.0
    duplicate = clients["recomendacion"].post("/recomendaciones", headers=headers, json={"solicitud_id": "recommend-0001", "sesion_id": sid})
    assert duplicate.json()["_id"] == rec["_id"]
    room, code = activate(system, student, sid)
    assert clients["sesiones"].post(f"/sesiones/{sid}/canje", json={"codigo": code}).status_code == 403
    assert clients["usuarios"].get("/perfiles/me", headers=room).status_code == 401
    assert clients["sesiones"].post(f"/sesiones/{sid}/estado", headers=headers, json={"estado": "finalizada"}).status_code == 403
    contents = clients["sesiones"].get(f"/audios/{audio['_id']}/contenido?sesion_id={sid}", headers={**headers, "Range": "bytes=0-9"})
    assert contents.status_code == 206, contents.text
    assert len(contents.content) == 10
    event = {"evento_id": "event-0001", "tipo": "reproduccion_inicio", "ocurrido_en": now().isoformat(), "datos": {
        "track_id": "track1", "audio_id": audio["_id"], "recomendacion_id": rec["_id"], "reproduccion_id": "playback-0001", "posicion_ms": 0, "volumen": .25}}
    response = clients["sesiones"].post(f"/sesiones/{sid}/eventos", headers=headers, json=event)
    assert response.status_code == 200, response.text
    assert clients["sesiones"].post(f"/sesiones/{sid}/eventos", headers=headers, json=event).json()["duplicado"]
    changed = copy.deepcopy(event)
    changed["datos"]["volumen"] = .5
    assert clients["sesiones"].post(f"/sesiones/{sid}/eventos", headers=headers, json=changed).status_code == 409
    feedback = {"solicitud_id": "feedback-0001", "recomendacion_id": rec["_id"], "track_id": "track1", "preferencia": "me_gusta", "molestia": False}
    result = clients["recomendacion"].post("/feedback", headers=headers, json=feedback)
    assert result.status_code == 201, result.text
    assert result.json()["estado_ajuste"] == "aplicado"
    version = db.perfiles.find_one({"usuario_id": ObjectId(uid)})["version"]
    assert clients["recomendacion"].post("/feedback", headers=headers, json=feedback).status_code == 201
    assert db.perfiles.find_one({"usuario_id": ObjectId(uid)})["version"] == version
    assert db.recomendaciones.find_one()["perfil_utilizado"]["version"] == 2
    # Simular pérdida de confirmación: perfil ya aplicado, feedback aún pendiente.
    db.feedback.update_one({}, {"$set": {"estado_ajuste": "pendiente"}})
    assert clients["recomendacion"].post(f"/feedback/{result.json()['_id']}/reintentar", headers=headers).json()["estado_ajuste"] == "aplicado"
    assert db.perfiles.find_one({"usuario_id": ObjectId(uid)})["version"] == version
    feedback.update(solicitud_id="feedback-0002", preferencia="no_me_gusta")
    assert clients["recomendacion"].post("/feedback", headers=headers, json=feedback).json()["estado_ajuste"] == "sin_cambio"
    assert db.perfiles.find_one({"usuario_id": ObjectId(uid)})["version"] == version
    assert clients["sesiones"].post(f"/sesiones/{sid}/estado", headers=room, json={"estado": "finalizada"}).status_code == 200
    assert clients["sesiones"].post(f"/sesiones/{sid}/encuesta", headers=headers, json={"cuestionario_version": "cuestionario-v1-borrador", "respuestas": []}).status_code == 503
    real_config = config("cuestionario-v1")
    real_config["aprobado"] = True  # Solo fixture, NO modifica el archivo.
    monkeypatch.setattr(sessions_module, "config", lambda name: real_config if name == "cuestionario-v1" else config(name))
    survey = {"cuestionario_version": real_config["version"], "respuestas": [{"pregunta_id": x["pregunta_id"], "valor": 3} for x in real_config["preguntas"]]}
    response = clients["sesiones"].post(f"/sesiones/{sid}/encuesta", headers=headers, json=survey)
    assert response.status_code == 201, response.text
    assert "resultados_por_dimension" not in response.json()
    exported = clients["sesiones"].get("/investigacion/exportacion", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "student@example" not in exported.text and "password_hash" not in exported.text and "codigo_hash" not in exported.text


def test_audio_mutation_and_traversal(system, student):
    clients, _, path = system
    headers, _ = student
    sid, rec, audio = prepare(system, student)
    bad = clients["sesiones"].post("/audios", headers=headers, json={"tipo": "cancion", "track_id": "track1", "ubicacion": "../escape.wav",
        "fuente_autorizada": True, "correspondencia_verificada": True})
    assert bad.status_code == 422
    (path / "test.wav").write_bytes(b"changed")
    assert clients["sesiones"].get(f"/audios/{audio['_id']}/contenido?sesion_id={sid}", headers=headers).status_code == 409


def test_other_user_cannot_read(system, student):
    clients, db, _ = system
    sid, rec, _ = prepare(system, student)
    other = db.usuarios.insert_one({"email": "other@test.test", "rol": "estudiante", "estado": "activo", "mayor_edad_confirmado": True,
        "consentimiento": {"aceptado": True, "version": "consentimiento-v1"}}).inserted_id
    headers = {"Authorization": "Bearer " + token(other)}
    assert clients["sesiones"].get(f"/sesiones/{sid}", headers=headers).status_code == 403
    assert clients["recomendacion"].get(f"/recomendaciones/{rec['_id']}", headers=headers).status_code == 403
    assert clients["sesiones"].get("/investigacion/exportacion", headers=headers).status_code == 403


def test_missing_features_and_heuristic_not_measurement():
    rules = config("reglas-v1")
    profile = {"afinidad_aprendida": {"energy": .2, "valence": .4}}
    assert frequency_category({"energy": .9}) is None
    assert frequency_category({"acousticness": .9}) == "Medios"
    result = rank({"id": "x", "energy": 0.0}, profile, set(), rules)
    assert result["atributos_utilizados"]["valence"] is None
    assert result["atributos_utilizados"]["energy"] == 0
    assert result["puntaje_compatibilidad"] == 97
    assert result["ajuste_frecuencial"] == 0


def test_profile_version_conflict_and_unknown_artist(system, student):
    clients, db, _ = system
    headers, uid = student
    assert clients["usuarios"].put("/perfiles/me", headers=headers, json={"version_esperada": 1, "artistas_preferidos": ["missing"]}).status_code == 422
    assert clients["usuarios"].put("/perfiles/me", headers=headers, json={"version_esperada": 99}).status_code == 409
    sid, _, _ = prepare(system, student)
    clients["usuarios"].put("/perfiles/me", headers=headers, json={"version_esperada": 2})
    assert clients["recomendacion"].post("/recomendaciones", headers=headers, json={"solicitud_id": "new-rec-0002", "sesion_id": sid}).status_code == 409


def test_tones_approved_fixture_omissions_and_heuristic(system, student, monkeypatch):
    clients, db, path = system
    headers, uid = student
    prepare(system, student)
    cfg = config("tonos-v1")
    cfg["aprobado"] = True  # Exclusivamente fixture: no aprobación científica.
    for tone in cfg["tonos"]:
        tone["duracion_ms"] = 1000
        response = clients["sesiones"].post("/audios", headers=headers, json={"tipo": "tono", "tono_id": tone["tono_id"],
            "ubicacion": "test.wav", "correspondencia_verificada": True, "fuente_autorizada": True})
        assert response.status_code == 201, response.text
    monkeypatch.setattr(users_module, "config", lambda name: cfg if name == "tonos-v1" else config(name))
    response = clients["usuarios"].post("/evaluaciones-tonos", headers=headers)
    assert response.status_code == 201, response.text
    evaluation = response.json()
    answers = [{"tono_id": t["tono_id"], "audio_id": evaluation["audios_utilizados"][t["tono_id"]]["audio_id"],
        "frecuencia_hz": t["frecuencia_hz"], "orden": i + 1, "agrado": 2, "molestia": 4, "omitido": False} for i, t in enumerate(cfg["tonos"])]
    answers[0].update(omitido=True, agrado=None, molestia=None)
    bad = copy.deepcopy(answers)
    bad[0]["agrado"] = 0
    url = f"/evaluaciones-tonos/{evaluation['_id']}"
    assert clients["usuarios"].put(url, headers=headers, json={"estado": "completada", "respuestas": bad}).status_code == 422
    bad = copy.deepcopy(answers)
    bad[1]["frecuencia_hz"] = 500
    assert clients["usuarios"].put(url, headers=headers, json={"estado": "completada", "respuestas": bad}).status_code == 422
    payload = {"estado": "completada", "respuestas": answers}
    assert clients["usuarios"].put(url, headers=headers, json=payload).status_code == 200
    assert clients["usuarios"].put(url, headers=headers, json=payload).status_code == 200
    session = clients["sesiones"].post("/sesiones", headers=headers, json={"solicitud_id": "heuristic-0002", "actividad": {"id": "test"}, "modalidad": "personalizada_heuristica"})
    assert session.status_code == 201, session.text
    response = clients["recomendacion"].post("/recomendaciones", headers=headers, json={"solicitud_id": "heuristic-rec-0002", "sesion_id": session.json()["_id"]})
    assert response.status_code == 201, response.text
    assert response.json()["canciones"][0]["ajuste_frecuencial"] == -300
    assert response.json()["canciones"][0]["categoria_frecuencial_inferida"] == "Medios"
    assert response.json()["evaluacion_tonos_utilizada"]["_id"] == evaluation["_id"]


def test_pending_feedback_resumes_after_peer_failure(system, student):
    from fastapi import HTTPException
    clients, db, _ = system
    headers, uid = student
    sid, rec, _ = prepare(system, student)
    activate(system, student, sid)
    app = clients["recomendacion"].app
    original = app.state.peer_override
    def unavailable(target, method, path, body):
        if "/ajustes" in path:
            raise HTTPException(503, "Servicio no disponible")
        return original(target, method, path, body)
    app.state.peer_override = unavailable
    data = {"solicitud_id": "pending-feedback-001", "recomendacion_id": rec["_id"], "track_id": "track1", "preferencia": "me_gusta"}
    assert clients["recomendacion"].post("/feedback", headers=headers, json=data).status_code == 503
    assert db.feedback.count_documents({"estado_ajuste": "pendiente"}) == 1
    app.state.peer_override = original
    result = clients["recomendacion"].post("/feedback", headers=headers, json=data)
    assert result.status_code == 201, result.text
    assert result.json()["estado_ajuste"] == "aplicado"
    assert db.feedback.count_documents({}) == 1


def test_code_expiration_attempts_and_room_scope(system, student):
    clients, db, _ = system
    headers, uid = student
    sid, _, _ = prepare(system, student)
    clients["sesiones"].post(f"/sesiones/{sid}/vinculacion", headers=headers)
    for _ in range(6):
        assert clients["sesiones"].post(f"/sesiones/{sid}/canje", json={"codigo": "x" * 43}).status_code == 403
    assert db.sesiones.find_one({"_id": ObjectId(sid)})["vinculacion"]["intentos"] == 5
    code = clients["sesiones"].post(f"/sesiones/{sid}/vinculacion", headers=headers).json()["codigo"]
    db.sesiones.update_one({"_id": ObjectId(sid)}, {"$set": {"vinculacion.caduca_en": now() - timedelta(seconds=1)}})
    assert clients["sesiones"].post(f"/sesiones/{sid}/canje", json={"codigo": code}).status_code == 403
    room, _ = activate(system, student, sid)
    other = clients["sesiones"].post("/sesiones", headers=headers, json={"solicitud_id": "second-session-001", "actividad": {"id": "test"}}).json()["_id"]
    assert clients["sesiones"].get(f"/sesiones/{other}", headers=room).status_code == 403


def test_large_request_and_reused_id_rejected(system, student):
    clients, _, _ = system
    headers, _ = student
    sid, _, _ = prepare(system, student)
    result = clients["sesiones"].post("/sesiones", headers=headers, json={"solicitud_id": "session-0001", "actividad": {"id": "changed"}})
    assert result.status_code == 409
    result = clients["usuarios"].post("/auth/login", content=b"x" * 65537)
    assert result.status_code == 413
