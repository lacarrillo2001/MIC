"""Resolución de títulos públicos, sin enviar perfiles ni extraer audio."""
import html
import math
import os
import re
import threading
import unicodedata
from datetime import timedelta, timezone

import httpx
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from shared.runtime import clean, fingerprint, now

_search_lock = threading.Lock()
VERSIONS = {"cover", "covers", "remix", "live", "karaoke", "nightcore", "slowed", "sped", "instrumental", "acapella", "acoustic"}


def configured():
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    return bool(key and not key.startswith(("REEMPLAZAR", "TU_CLAVE")))


def daily_limit():
    try:
        return max(1, min(1000, int(os.environ.get("YOUTUBE_MAX_SEARCHES_PER_DAY", "50"))))
    except ValueError:
        return 50


def normalized(text):
    text = unicodedata.normalize("NFKD", html.unescape(str(text))).lower()
    return " ".join(re.findall(r"[a-z0-9]+", "".join(x for x in text if not unicodedata.combining(x))))


def duration_seconds(value):
    match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return None
    days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def comparable_video(song, video, region):
    snippet, status, details = video.get("snippet", {}), video.get("status", {}), video.get("contentDetails", {})
    vid = video.get("id", "")
    if not isinstance(vid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
        return False
    if status.get("embeddable") is not True or status.get("privacyStatus") != "public" or status.get("uploadStatus") != "processed":
        return False
    if snippet.get("liveBroadcastContent", "none") != "none" or details.get("contentRating", {}).get("ytRating") == "ytAgeRestricted":
        return False
    restriction = details.get("regionRestriction", {})
    if region in restriction.get("blocked", []) or ("allowed" in restriction and region not in restriction["allowed"]):
        return False
    title, expected = normalized(snippet.get("title", "")), normalized(song["name"])
    artist = normalized(song["artists"][0])
    artist_context = title + " " + normalized(snippet.get("channelTitle", ""))
    if not artist or not re.search(r"(?:^|\s)" + re.escape(artist) + r"(?:$|\s)", artist_context):
        return False
    title_words = set(expected.split()) - {"the", "a", "an", "feat", "ft"}
    if not title_words or not title_words.issubset(set(title.split())):
        return False
    if (set(title.split()) & VERSIONS) - set(expected.split()):
        return False
    seconds = duration_seconds(details.get("duration"))
    expected_seconds = song["duration_ms"] / 1000
    return seconds is not None and abs(seconds - expected_seconds) <= max(8, expected_seconds * .05)


def reserve_search(db):
    current = now()
    key = "__presupuesto__" + current.strftime("%Y-%m-%d")
    try:
        result = db.youtube_vinculos.find_one_and_update(
            {"track_id": key, "consultas": {"$lt": daily_limit()}},
            {"$inc": {"consultas": 1}, "$setOnInsert": {"tipo": "presupuesto", "caduca_en": current + timedelta(days=2)}},
            upsert=True, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        raise HTTPException(429, "Se alcanzó el límite diario local de búsquedas de YouTube; inténtalo otro día")
    return result


def api_get(client, resource, params):
    try:
        response = client.get("https://www.googleapis.com/youtube/v3/" + resource, params=params,
                              headers={"X-Goog-Api-Key": os.environ["YOUTUBE_API_KEY"].strip()}, timeout=4)
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "YouTube no respondió; no se ha inventado una coincidencia") from None
    if not isinstance(data, dict):
        raise HTTPException(502, "Respuesta de YouTube no válida")
    if response.status_code >= 400:
        reasons = {x.get("reason") for x in data.get("error", {}).get("errors", []) if isinstance(x, dict)}
        if reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"} or response.status_code == 429:
            raise HTTPException(429, "La cuota de YouTube no permite continuar las búsquedas")
        raise HTTPException(503, "YouTube rechazó la solicitud. Revisar la clave del servidor y que YouTube Data API v3 esté habilitada")
    if not isinstance(data, dict) or not isinstance(data.get("items", []), list):
        raise HTTPException(502, "Respuesta de YouTube no válida")
    return data.get("items", [])


def resolve_video(db, song, client=None):
    if not configured():
        raise HTTPException(503, "Falta configurar YOUTUBE_API_KEY en el backend; no pegar la clave en el navegador ni en el chat")
    duration = song.get("duration_ms")
    if not isinstance(song.get("name"), str) or not song["name"].strip() or not song.get("artists") or not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration <= 0:
        return {"estado": "sin_coincidencia", "track_id": song["track_id"], "motivo": "Faltan título, artista o duración del catálogo"}
    signature = fingerprint({k: song.get(k) for k in ("track_id", "name", "artists", "duration_ms")})
    region = os.environ.get("YOUTUBE_REGION", "EC").upper()
    if not re.fullmatch(r"[A-Z]{2}", region):
        raise HTTPException(503, "Configurar YOUTUBE_REGION con un código de país de dos letras")
    signature = fingerprint({"fuente": signature, "region": region, "reglas": "youtube-match-v1"})

    def cached():
        item = db.youtube_vinculos.find_one({"track_id": song["track_id"], "firma_fuente": signature})
        if item and item["caduca_en"].replace(tzinfo=timezone.utc) > now():
            return clean(item["resultado"])
        return None

    old = cached()
    if old:
        return old
    if not _search_lock.acquire(blocking=False):
        raise HTTPException(503, "Hay otra búsqueda en curso; reintentar sin crear otra lista")
    owned = client is None
    try:
        old = cached()
        if old:
            return old
        reserve_search(db)
        client = client or httpx.Client()
        query = f"{song['name']} {song['artists'][0]}"[:250]
        items = api_get(client, "search", {"part": "snippet", "type": "video", "q": query, "maxResults": 5,
            "videoEmbeddable": "true", "videoSyndicated": "true", "regionCode": region, "safeSearch": "moderate"})
        ids = [x.get("id", {}).get("videoId") for x in items if isinstance(x.get("id"), dict)]
        ids = [x for x in ids if isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", x)]
        details = api_get(client, "videos", {"part": "snippet,contentDetails,status", "id": ",".join(ids)}) if ids else []
        eligible = [x for x in details if x.get("id") in ids and comparable_video(song, x, region)]
        # Determinista: escoger la duración más próxima; no usar popularidad de YouTube.
        eligible.sort(key=lambda x: (abs(duration_seconds(x["contentDetails"]["duration"]) - duration / 1000), x["id"]))
        result = {"estado": "sin_coincidencia", "track_id": song["track_id"], "motivo": "No se encontró un video público insertable con título, artista, versión y duración compatibles"}
        if eligible:
            video = eligible[0]
            result = {"estado": "disponible", "track_id": song["track_id"], "video_id": video["id"],
                "titulo_youtube": html.unescape(video["snippet"]["title"]), "canal": video["snippet"].get("channelTitle", ""),
                "coincidencia": "probable_automatica", "verificacion_acustica": False,
                "advertencia": "Coincidencia por metadatos, no prueba de que sea la misma grabación"}
        current = now()
        db.youtube_vinculos.update_one({"track_id": song["track_id"]}, {"$set": {
            "tipo": "vinculo", "firma_fuente": signature, "resultado": result, "consultado_en": current,
            "caduca_en": current + (timedelta(days=7) if eligible else timedelta(hours=6))}}, upsert=True)
        return result
    finally:
        if owned and client:
            client.close()
        _search_lock.release()
