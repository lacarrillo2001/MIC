"""Audio bajo demanda: trabajos acotados, caché local y conversión MP3 real."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import Field
from shared.runtime import Model, dbof, identity, peer, ensure_owner, get_document, now

router = APIRouter(prefix='/descargas', tags=['Audio web'])
pool = ThreadPoolExecutor(max_workers=1)
pending = set()
guard = threading.Lock()


class Download(Model):
    recomendacion_id: str = Field(pattern=r'^[a-f0-9]{24}$')
    track_id: str = Field(min_length=1, max_length=100)


def participant(request):
    user = identity(request)
    peer(request, 'usuarios', 'GET', f"/internal/usuarios/{user['sub']}/contexto")
    return user


def authorized_song(request, rec_id, tid):
    if not re.fullmatch(r'[a-f0-9]{24}', rec_id):
        raise HTTPException(422, 'Identificador de recomendación inválido')
    user = participant(request)
    rec = peer(request, 'recomendacion', 'GET', f'/internal/recomendaciones/{rec_id}')
    ensure_owner(rec, user)
    if rec.get('tipo') != 'youtube_web':
        raise HTTPException(409, 'La descarga bajo demanda requiere una lista web')
    song = next((s for s in rec['canciones'] if s['track_id'] == tid), None)
    if not song:
        raise HTTPException(422, 'Canción no incluida en la lista')
    return song


def cache_key(song):
    return 'web:' + hashlib.sha256(json.dumps({k: song.get(k) for k in ('track_id', 'name', 'artists', 'duration_ms')}, sort_keys=True).encode()).hexdigest()


def public(item):
    return {'audio_id': str(item['_id']), 'estado': item['estado_descarga'], 'error': item.get('error_descarga'),
            'duracion_ms': item.get('duracion_ms'), 'analisis_acustico': item.get('analisis_acustico', 'pendiente')}


def run_command(args, timeout):
    # No cookies, proxy, credenciales, descarga de playlists ni evasión de errores de acceso.
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=True)


def prepare_audio(db, audio_id, song):
    root = Path(os.environ.get('MEDIA_ROOT', '/media')).resolve() / 'descargas'
    work = root / str(audio_id)
    try:
        work.mkdir(parents=True, exist_ok=True)
        query = f"{song['name']} {song['artists'][0]}"
        result = run_command(['yt-dlp', '--ignore-config', '--no-playlist', '--flat-playlist', '--skip-download', '--dump-single-json',
                              '--socket-timeout', '15', '--retries', '1', f'ytsearch5:{query}'], 90)
        entries = json.loads(result.stdout).get('entries', [])
        from sesiones.match_audio import choose_video
        chosen = choose_video(song, entries)
        if not chosen:
            raise ValueError('Sin coincidencia de título, artista, versión y duración')
        run_command(['yt-dlp', '--ignore-config', '--js-runtimes', 'node', '--no-playlist', '--max-filesize', '80M', '--socket-timeout', '15',
                     '--retries', '1', '-f', 'bestaudio', '-x', '--audio-format', 'mp3', '--audio-quality', '5',
                     '-o', str(work / 'audio.%(ext)s'), 'https://www.youtube.com/watch?v=' + chosen['id']], 180)
        path = work / 'audio.mp3'
        if not path.is_file() or path.stat().st_size > 80 * 1024 * 1024:
            raise ValueError('Archivo ausente o tamaño no permitido')
        info = json.loads(run_command(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,codec_type',
                                      '-of', 'json', str(path)], 15).stdout)
        if not any(s.get('codec_name') == 'mp3' and s.get('codec_type') == 'audio' for s in info['streams']):
            raise ValueError('La conversión no produjo MP3 válido')
        duration = round(float(info['format']['duration']) * 1000)
        if abs(duration - song['duration_ms']) > max(8000, song['duration_ms'] * .05):
            raise ValueError('Duración del archivo incompatible con el catálogo')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        db.audios.update_one({'_id': audio_id}, {'$set': {'estado_descarga': 'disponible', 'disponible': True,
            'ubicacion': str(path.relative_to(root.parent)), 'formato': 'audio/mpeg', 'duracion_ms': duration,
            'hash_archivo': digest, 'video_id': chosen['id'], 'titulo_fuente': chosen['title'],
            'coincidencia': 'probable_por_metadatos', 'analisis_acustico': 'pendiente', 'error_descarga': None,
            'actualizado_en': now()}})
    except Exception as exc:
        # No divulgar stderr: puede contener direcciones o datos internos del proveedor.
        detail = str(getattr(exc, 'stderr', '') or '').lower()
        category = 'acceso_rechazado' if any(t in detail for t in ('403', 'sign in', 'confirm you', 'private video', 'login required')) else type(exc).__name__
        db.audios.update_one({'_id': audio_id}, {'$set': {'estado_descarga': 'error', 'disponible': False, 'tipo_error': category,
            'error_descarga': 'No se pudo obtener un audio compatible. La fuente puede rechazar la descarga; puedes usar el reproductor oficial de YouTube.',
            'actualizado_en': now()}})
        for path in work.glob('*'):
            if path.is_file():
                path.unlink(missing_ok=True)
    finally:
        with guard:
            pending.discard(str(audio_id))


@router.post('', status_code=202)
def start(body: Download, request: Request):
    song = authorized_song(request, body.recomendacion_id, body.track_id)
    if not song.get('name') or not song.get('artists') or not isinstance(song.get('duration_ms'), (int, float)) or not 15000 <= song['duration_ms'] <= 1200000:
        raise HTTPException(422, 'Se requiere título, artista y duración entre 15 segundos y 20 minutos')
    db = dbof(request)
    key = cache_key(song)
    with guard:
        item = db.audios.find_one({'cache_key': key})
        if item and item.get('estado_descarga') == 'disponible':
            path = Path(os.environ.get('MEDIA_ROOT', '/media')) / item['ubicacion']
            if path.is_file():
                return public(item)
        if item and str(item['_id']) in pending:
            return public(item)
        if pending:
            raise HTTPException(429, 'Hay otra descarga en curso. Espera a que termine.')
        data = {'tipo': 'cancion', 'track_id': body.track_id, 'cache_key': key, 'estado_descarga': 'descargando',
                'disponible': False, 'fuente': 'youtube_descarga', 'fuente_autorizada': False,
                'correspondencia_verificada': False, 'analisis_acustico': 'pendiente', 'actualizado_en': now()}
        if item:
            db.audios.update_one({'_id': item['_id']}, {'$set': data})
            audio_id = item['_id']
        else:
            audio_id = db.audios.insert_one(data).inserted_id
        pending.add(str(audio_id))
        pool.submit(prepare_audio, db, audio_id, song)
    return public(db.audios.find_one({'_id': audio_id}))


def owned_audio(request, audio_id, rec_id):
    item = get_document(dbof(request).audios, audio_id)
    song = authorized_song(request, rec_id, item.get('track_id'))
    if item.get('cache_key') != cache_key(song):
        raise HTTPException(403, 'Audio ajeno a esta canción')
    return item


@router.get('/{audio_id}')
def status(audio_id: str, recomendacion_id: str, request: Request):
    return public(owned_audio(request, audio_id, recomendacion_id))


@router.get('/{audio_id}/contenido')
def content(audio_id: str, recomendacion_id: str, request: Request):
    item = owned_audio(request, audio_id, recomendacion_id)
    if item['estado_descarga'] != 'disponible':
        raise HTTPException(409, 'Audio no disponible')
    root = Path(os.environ.get('MEDIA_ROOT', '/media')).resolve()
    path = (root / item['ubicacion']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(409, 'Archivo no disponible')
    return FileResponse(path, media_type='audio/mpeg')
