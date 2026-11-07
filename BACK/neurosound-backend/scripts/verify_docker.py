"""Prueba real aislada: no importa ni modifica datos del entorno de desarrollo.

Ejecutar con .venv/Scripts/python scripts/verify_docker.py. Requiere Compose
compatible con !override, las imágenes construidas y permisos de Docker.
"""
import json
import secrets
import subprocess
import time
import wave
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "neurosound-verificacion"
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", "docker-compose.yml", "-f", "docker-compose.test.yml"]


def run(args, *, capture=True):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=capture)
    if result.returncode:
        # No imprimir environment ni secretos. Los comandos solo contienen fixtures.
        raise RuntimeError(f"Comando falló: {' '.join(args[:6])}: {(result.stderr or '')[-1800:]}")
    return result.stdout.strip() if capture else ""


def exec_python(service, code):
    return run(COMPOSE + ["exec", "-T", service, "python", "-c", code])


def api(port, method, path, body=None, headers=None, expected=200):
    response = httpx.request(method, f"http://127.0.0.1:{port}{path}", json=body, headers=headers, timeout=20)
    if response.status_code != expected:
        raise AssertionError(f"{method} {path}: {response.status_code} (esperado {expected})")
    return response.json()


def wait_healthy():
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            for port in (18001, 18002, 18003):
                api(port, "GET", "/health/ready")
            return
        except (httpx.HTTPError, AssertionError):
            time.sleep(1)
    raise AssertionError("Las APIs de verificación no se prepararon")


def main():
    if run(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"]) or run(
            ["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={PROJECT}"]):
        raise SystemExit("Ya existen recursos del proyecto de verificación. Revisarlos antes; no se borran automáticamente.")
    media = ROOT / "tests" / "runtime-media"
    media.mkdir(exist_ok=True)
    audio_file = media / "verify-generated.wav"
    if audio_file.exists():
        raise SystemExit("Ya existe el audio de verificación; revisar antes de continuar")
    with wave.open(str(audio_file), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\0\0" * 8000)
    started = False
    try:
        print("Arrancando proyecto aislado de verificación...", flush=True)
        started = True
        run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "180"])
        password = secrets.token_urlsafe(20)
        uid = api(18001, "POST", "/auth/registro", {"email": "verificacion@example.test", "password": password,
            "mayor_edad_confirmado": True, "consentimiento_aceptado": True, "consentimiento_version": "consentimiento-v1"}, expected=201)["usuario_id"]
        login = api(18001, "POST", "/auth/login", {"email": "verificacion@example.test", "password": password})
        headers = {"Authorization": "Bearer " + login["access_token"]}
        exec_python("usuarios", "from shared.manage import connect; from bson import ObjectId; "
                    f"connect().usuarios.update_one({{'_id':ObjectId('{uid}')}},{{'$set':{{'rol':'investigador'}}}})")
        exec_python("recomendacion", "from shared.manage import connect; d=connect(); "
                    "d.artists.insert_one({'id':'verify-artist','name':'Synthetic','genres':['piano']}); "
                    "d.songsV2.insert_one({'idros':'verify-track','name':'Synthetic','id_artists':['verify-artist'],"
                    "'artists':['Synthetic'],'energy':0.0,'valence':0.3,'tempo':80,'acousticness':0.9})")
        api(18001, "PUT", "/perfiles/me", {"version_esperada": 1, "artistas_preferidos": ["verify-artist"],
            "generos_preferidos": ["piano"], "tempo_preferido": "lento"}, headers)
        audio = api(18003, "POST", "/audios", {"tipo": "cancion", "track_id": "verify-track", "ubicacion": "verify-generated.wav",
            "correspondencia_verificada": True, "fuente_autorizada": True}, headers, 201)
        session = api(18003, "POST", "/sesiones", {"solicitud_id": "verify-session-001", "actividad": {"id": "synthetic", "version": "test"}}, headers, 201)
        sid = session["_id"]
        request = {"solicitud_id": "verify-rec-001", "sesion_id": sid}
        rec = api(18002, "POST", "/recomendaciones", request, headers, 201)
        assert api(18002, "POST", "/recomendaciones", request, headers, 201)["_id"] == rec["_id"]
        code = api(18003, "POST", f"/sesiones/{sid}/vinculacion", headers=headers)["codigo"]
        room_token = api(18003, "POST", f"/sesiones/{sid}/canje", {"codigo": code})["access_token"]
        room = {"Authorization": "Bearer " + room_token}
        api(18003, "POST", f"/sesiones/{sid}/estado", {"estado": "activa"}, room)
        response = httpx.get(f"http://127.0.0.1:18003/audios/{audio['_id']}/contenido?sesion_id={sid}", headers={**headers, "Range": "bytes=0-9"})
        assert response.status_code == 206 and len(response.content) == 10
        feedback = {"solicitud_id": "verify-feedback-001", "recomendacion_id": rec["_id"], "track_id": "verify-track", "preferencia": "me_gusta"}
        assert api(18002, "POST", "/feedback", feedback, headers, 201)["estado_ajuste"] == "aplicado"
        version = api(18001, "GET", "/perfiles/me", headers=headers)["version"]
        api(18002, "POST", "/feedback", feedback, headers, 201)
        assert api(18001, "GET", "/perfiles/me", headers=headers)["version"] == version
        api(18003, "POST", f"/sesiones/{sid}/estado", {"estado": "finalizada"}, room)
        api(18001, "POST", "/evaluaciones-tonos", headers=headers, expected=503)
        api(18003, "POST", f"/sesiones/{sid}/encuesta", {"cuestionario_version": "cuestionario-v1-borrador", "respuestas": []}, headers, 503)
        exported = api(18003, "GET", "/investigacion/exportacion", headers=headers)
        assert "verificacion@example" not in json.dumps(exported)
        print("Flujo real, audio Range, feedback y bloqueos: OK", flush=True)
        for service, forbidden in (("usuarios", "songsV2"), ("recomendacion", "usuarios"), ("sesiones", "perfiles")):
            code = ("from shared.manage import connect\nfrom pymongo.errors import OperationFailure\n"
                    "try:\n connect()['" + forbidden + "'].find_one({})\nexcept OperationFailure as e:\n assert e.code==13\n print('aislado')\nelse:\n raise AssertionError('Acceso cruzado permitido')")
            assert exec_python(service, code) == "aislado"
        print("Aislamiento de permisos MongoDB: OK", flush=True)
        # Solo elimina una colección vacía del proyecto temporal para verificar recreación.
        js = "db.getSiblingDB('admin').auth('root',process.env.MONGO_INITDB_ROOT_PASSWORD); const d=db.getSiblingDB('neurosound'); if(d.encuestas.countDocuments({})!==0) throw Error('No vacia'); d.encuestas.drop();"
        run(COMPOSE + ["exec", "-T", "mongo", "mongosh", "--quiet", "--eval", js])
        run(COMPOSE + ["restart", "mongo", "usuarios", "recomendacion", "sesiones"])
        wait_healthy()
        assert api(18001, "GET", "/perfiles/me", headers=headers)["version"] == version
        assert api(18003, "GET", f"/sesiones/{sid}", headers=headers)["estado"] == "finalizada"
        assert api(18002, "GET", f"/recomendaciones/{rec['_id']}", headers=headers)["_id"] == rec["_id"]
        js = "db.getSiblingDB('admin').auth('root',process.env.MONGO_INITDB_ROOT_PASSWORD); const d=db.getSiblingDB('neurosound'); if(d.getCollectionNames().length!==11 || !d.getCollectionNames().includes('encuestas')) throw Error('Colecciones'); print('11 colecciones');"
        assert "11 colecciones" in run(COMPOSE + ["exec", "-T", "mongo", "mongosh", "--quiet", "--eval", js])
        print("Reinicio de MongoDB y APIs: datos conservados, colección faltante recreada: OK", flush=True)
        print("VERIFICACIÓN DOCKER COMPLETADA", flush=True)
    finally:
        if started:
            # Nombre fijo y recursos cuya ausencia se comprobó ANTES de crearlos.
            run(COMPOSE + ["down", "-v", "--remove-orphans"])
            print("Contenedores y volumen temporales de verificación retirados; desarrollo intacto.", flush=True)
        audio_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
