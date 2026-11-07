"""Ejecuta las APIs Python existentes contra una base SIMULADA y WAV temporal.

No abre MongoDB, no lee .env, no modifica las fuentes del backend.
"""
import argparse
import hashlib
import json
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

import httpx
import mongomock
import uvicorn
from fastapi import HTTPException

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
args = parser.parse_args()
sys.path.insert(0, str(Path(args.source).resolve()))
for key in ("JWT_SECRET", "USUARIOS_SERVICE_KEY", "RECOMENDACION_SERVICE_KEY", "SESIONES_SERVICE_KEY"):
    os.environ[key] = secrets.token_hex(32)

from usuarios.app import build_app as users_app
from recomendacion.app import build_app as catalogue_app
from sesiones.app import build_app as sessions_app

db = mongomock.MongoClient(tz_aware=True).studyroom_test
original_create = type(db).create_collection


def mock_create(self, name, **kwargs):
    kwargs.pop("check_exists", None)
    return original_create(self, name, **kwargs)


type(db).create_collection = mock_create
servers, threads, sockets, bases = [], [], [], {}
for service in ("usuarios", "recomendacion", "sesiones"):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sockets.append(sock)
    bases[service] = f"http://127.0.0.1:{sock.getsockname()[1]}"


def dispatch(caller):
    def call(target, method, path, body):
        response = httpx.request(method, bases[target] + path, json=body, timeout=10,
            headers={"X-Service-Name": caller, "X-Service-Key": os.environ[f"{caller.upper()}_SERVICE_KEY"]})
        if response.is_error:
            raise HTTPException(response.status_code, response.json()["detail"])
        return response.json()
    return call


with tempfile.TemporaryDirectory(prefix="studyroom-http-") as folder:
    os.environ["MEDIA_ROOT"] = folder
    audio = Path(folder) / "fixture.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\0\0" * 8000)
    db.artists.insert_one({"id": "http-artist", "name": "Artista de prueba HTTP", "genres": ["ambient"]})
    db.songsV2.insert_one({"idros": "http-track", "name": "WAV sintético", "artists": ["Artista de prueba HTTP"],
        "id_artists": ["http-artist"], "energy": 0.0, "valence": .3, "tempo": 80, "acousticness": .9})
    db.audios.insert_one({"tipo": "cancion", "track_id": "http-track", "ubicacion": "fixture.wav",
        "formato": "audio/wav", "duracion_ms": 1000, "hash_archivo": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "disponible": True, "fuente_autorizada": True, "correspondencia_verificada": True})
    try:
        for (service, factory), sock in zip((("usuarios", users_app), ("recomendacion", catalogue_app), ("sesiones", sessions_app)), sockets):
            server = uvicorn.Server(uvicorn.Config(factory(db, dispatch(service)), log_level="error", access_log=False))
            servers.append(server)
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
            threads.append(thread)
            thread.start()
        deadline = time.monotonic() + 30
        while not all(server.started for server in servers):
            if time.monotonic() > deadline:
                raise RuntimeError("No iniciaron las APIs Python de prueba")
            time.sleep(.05)
        print(json.dumps({"usuarios": bases["usuarios"], "catalogo": bases["recomendacion"], "sesiones": bases["sesiones"]}), flush=True)
        sys.stdin.readline()
    finally:
        for server in servers:
            server.should_exit = True
        for thread in threads:
            thread.join(15)
        for sock in sockets:
            sock.close()
