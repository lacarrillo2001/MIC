import copy
from datetime import timedelta

import httpx
import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException

from recomendacion.youtube import comparable_video, duration_seconds, resolve_video
from shared.runtime import initialize, now, token


SONG = {"track_id": "track-a", "name": "Quiet River", "artists": ["Test Artist"], "duration_ms": 180000}
VIDEO = {"id": "abc12345678", "snippet": {"title": "Test Artist - Quiet River (Official Audio)", "channelTitle": "Test Artist - Topic", "liveBroadcastContent": "none"},
         "contentDetails": {"duration": "PT3M"}, "status": {"embeddable": True, "privacyStatus": "public", "uploadStatus": "processed"}}


def fake_client(calls, video=None, error=None):
    def handler(request):
        calls.append(request)
        assert request.headers["x-goog-api-key"] == "test-private-key"
        assert "test-private-key" not in str(request.url)
        if error:
            return httpx.Response(403, json={"error": {"errors": [{"reason": error}]}})
        if request.url.path.endswith("/search"):
            assert request.url.params["q"] == "Quiet River Test Artist"
            return httpx.Response(200, json={"items": [{"id": {"videoId": "abc12345678"}}]})
        return httpx.Response(200, json={"items": [video or VIDEO]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def cache_db():
    db = mongomock.MongoClient(tz_aware=True).test
    db.youtube_vinculos.create_index("track_id", unique=True)
    db.youtube_vinculos.create_index("caduca_en", expireAfterSeconds=0)
    return db


def test_match_rejects_wrong_artist_duration_and_versions():
    assert comparable_video(SONG, VIDEO, "EC")
    for title in ("Another Artist - Quiet River", "Test Artist - Quiet River Cover", "Test Artist - Quiet River Remix", "Test Artist - Quiet River Live"):
        bad = copy.deepcopy(VIDEO)
        bad["snippet"]["title"] = title
        bad["snippet"]["channelTitle"] = "Unknown channel"
        assert not comparable_video(SONG, bad, "EC")
    bad = copy.deepcopy(VIDEO)
    bad["contentDetails"]["duration"] = "PT6M"
    assert not comparable_video(SONG, bad, "EC")
    bad = copy.deepcopy(VIDEO)
    bad["status"]["embeddable"] = False
    assert not comparable_video(SONG, bad, "EC")
    assert duration_seconds("PT1H2M3S") == 3723


def test_cache_uses_metadata_only_and_reuses_without_search(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-private-key")
    db = cache_db()
    calls = []
    with fake_client(calls) as client:
        result = resolve_video(db, SONG, client)
        assert result["video_id"] == VIDEO["id"] and result["verificacion_acustica"] is False
        assert resolve_video(db, SONG, client) == result
        assert len(calls) == 2  # search + videos, no segunda consulta
    stored = db.youtube_vinculos.find_one({"track_id": SONG["track_id"]})
    assert stored["caduca_en"] < now() + timedelta(days=8)
    assert "test-private-key" not in repr(stored)
    assert db.songsV2.count_documents({}) == 0  # no escribe sobre el catálogo


def test_no_match_is_not_fabricated_and_quota_is_enforced(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-private-key")
    monkeypatch.setenv("YOUTUBE_MAX_SEARCHES_PER_DAY", "1")
    db = cache_db()
    bad = copy.deepcopy(VIDEO)
    bad["snippet"]["title"] += " cover"
    with fake_client([], bad) as client:
        assert resolve_video(db, SONG, client)["estado"] == "sin_coincidencia"
        with pytest.raises(HTTPException) as exc:
            resolve_video(db, {**SONG, "track_id": "another"}, client)
        assert exc.value.status_code == 429


def test_key_and_remote_errors_are_safe(monkeypatch):
    db = cache_db()
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        resolve_video(db, SONG)
    assert exc.value.status_code == 503
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-private-key")
    with fake_client([], error="quotaExceeded") as client:
        with pytest.raises(HTTPException) as exc:
            resolve_video(db, SONG, client)
    assert exc.value.status_code == 429
    assert "test-private-key" not in exc.value.detail


def test_web_playlist_without_local_audio_and_owner_protection(system, student, monkeypatch):
    clients, db, _ = system
    headers, uid = student
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-private-key")
    db.songsV2.insert_one({"id": SONG["track_id"], **{k: v for k, v in SONG.items() if k != "track_id"}, "id_artists": [], "tempo": 80})
    body = {"solicitud_id": "youtube-web-request", "limite": 5}
    api = clients["recomendacion"]
    result = api.post("/youtube/recomendaciones", headers=headers, json=body)
    assert result.status_code == 201, result.text
    rec = result.json()
    assert rec["tipo"] == "youtube_web" and rec["sesion_id"] is None
    assert db.sesiones.count_documents({}) == 0 and db.audios.count_documents({}) == 0
    assert api.post("/youtube/recomendaciones", headers=headers, json=body).json()["_id"] == rec["_id"]
    assert "test-private-key" not in api.get("/youtube/configuracion", headers=headers).text
    with fake_client([]) as client:
        api.app.state.youtube_http = client
        resolved = api.post(f"/youtube/recomendaciones/{rec['_id']}/resolver", headers=headers, json={"track_id": SONG["track_id"]})
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["estado"] == "disponible"
    assert api.post(f"/youtube/recomendaciones/{rec['_id']}/resolver", headers=headers, json={"track_id": "not-recommended"}).status_code == 422
    other = db.usuarios.insert_one({"estado": "activo", "rol": "estudiante", "mayor_edad_confirmado": True,
        "consentimiento": {"aceptado": True, "version": "consentimiento-v1"}}).inserted_id
    assert api.post(f"/youtube/recomendaciones/{rec['_id']}/resolver", headers={"Authorization": "Bearer " + token(other)}, json={"track_id": SONG["track_id"]}).status_code == 403
