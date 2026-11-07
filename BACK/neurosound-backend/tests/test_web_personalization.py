import copy

import mongomock
from bson import ObjectId

from recomendacion.selection import candidates, diverse, web_profile
from shared.runtime import config, now, token


def test_diversity_history_and_fallback():
    songs = [{'track_id': str(i), 'id_artists': [str(i // 3)], 'puntaje_compatibilidad': 100} for i in range(12)]
    result = diverse(songs, 5, 'seed', recent={'0', '1', '2'})
    assert len(result) == 5
    assert not {'0', '1', '2'}.intersection(x['track_id'] for x in result)
    assert all(sum(a in x['id_artists'] for x in result) <= 2 for a in ['1', '2', '3'])
    assert result == diverse(songs, 5, 'seed', recent={'0', '1', '2'})
    assert len(diverse(songs[:3], 3, 'seed', recent={'0', '1', '2'})) == 3
    assert len({x['track_id'] for x in diverse(songs, 12, 'seed')}) == 12
    assert diverse([dict(songs[0], puntaje_compatibilidad=200), *songs[1:]], 1, 'seed')[0]['track_id'] == '0'


def test_candidate_pools_reach_preferences_beyond_catalogue_start():
    db = mongomock.MongoClient().db
    db.songsV2.insert_many([{'id': f'old-{i}', 'id_artists': ['old'], 'tempo': 150} for i in range(1100)])
    db.songsV2.insert_one({'id': 'preferred', 'id_artists': ['favorite'], 'tempo': 95})
    profile = {'artistas_preferidos': ['favorite'], 'generos_preferidos': [], 'tempo_preferido': 'moderado'}
    result = candidates(db, profile, config('reglas-v1'))
    assert any(x['id'] == 'preferred' for x in result)
    assert len(result) <= 1000 and len({x['id'] for x in result}) == len(result)
    assert all(x['id'] != 'preferred' for x in candidates(db, profile, config('reglas-v1'), {'preferred'}))


def test_web_feedback_playback_correction_and_isolation(system, student, monkeypatch):
    clients, db, _ = system
    headers, uid = student
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-private-key')
    db.songsV2.insert_many([{'id': f'track-{i}', 'name': f'Song {i}', 'artists': [f'Artist {i}'],
        'id_artists': [f'a-{i}'], 'tempo': 95, 'energy': .8, 'valence': .6, 'duration_ms': 180000} for i in range(8)])
    api = clients['recomendacion']
    original_profile = copy.deepcopy(db.perfiles.find_one({'usuario_id': ObjectId(uid)}))
    def make(request_id):
        r = api.post('/youtube/recomendaciones', headers=headers, json={'solicitud_id': request_id, 'limite': 5})
        assert r.status_code == 201, r.text
        return r.json()
    rec = make('personalization-first')
    tid = rec['canciones'][0]['track_id']
    root = f"/youtube/recomendaciones/{rec['_id']}"
    body = {'track_id': tid, 'respuesta': 'me_gusta', 'revision': 0}
    assert api.post(root + '/feedback', headers=headers, json=body).status_code == 409
    assert api.post(root + '/reproduccion', headers=headers, json={'track_id': 'foreign'}).status_code == 422
    assert api.post(root + '/reproduccion', headers=headers, json={'track_id': tid}).status_code == 200
    first_time = db.recomendaciones.find_one({'_id': ObjectId(rec['_id'])})['ultima_reproduccion_en']
    assert api.post(root + '/reproduccion', headers=headers, json={'track_id': tid}).status_code == 200
    assert db.recomendaciones.find_one({'_id': ObjectId(rec['_id'])})['ultima_reproduccion_en'] == first_time
    saved = api.post(root + '/feedback', headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()['revision'] == 1
    assert api.post(root + '/feedback', headers=headers, json=body).json()['revision'] == 1
    assert db.feedback.count_documents({'tipo': 'youtube_web'}) == 1
    history = api.get('/youtube/feedback', headers=headers).json()
    assert len(history) == 1 and history[0]['track_id'] == tid
    assert api.get('/youtube/feedback?pagina=0', headers=headers).status_code == 422
    profile, excluded = web_profile(db, uid, original_profile, .1)
    assert profile['afinidad_aprendida']['energy'] == .8 and not excluded
    # Neutral retira la influencia anterior; un cambio no agrega un segundo ajuste.
    corrected = api.post(root + '/feedback', headers=headers, json={**body, 'respuesta': 'neutral', 'revision': 1})
    assert corrected.status_code == 200
    assert web_profile(db, uid, original_profile, .1)[0]['afinidad_aprendida'] == original_profile['afinidad_aprendida']
    assert api.post(root + '/feedback', headers=headers, json={**body, 'respuesta': 'molestia', 'revision': 1}).status_code == 409
    assert api.post(root + '/feedback', headers=headers, json={**body, 'respuesta': 'molestia', 'revision': 2}).status_code == 200
    later = make('personalization-second')
    assert tid not in [x['track_id'] for x in later['canciones']]
    assert db.recomendaciones.find_one({'_id': ObjectId(rec['_id'])})['canciones'] == rec['canciones']
    assert db.perfiles.find_one({'usuario_id': ObjectId(uid)}) == original_profile
    feedback_id = saved.json()['_id']
    assert api.post(f'/feedback/{feedback_id}/reintentar', headers=headers).status_code == 409
    other = db.usuarios.insert_one({'estado': 'activo', 'rol': 'estudiante', 'mayor_edad_confirmado': True,
        'consentimiento': {'aceptado': True, 'version': 'consentimiento-v1'}}).inserted_id
    other_headers = {'Authorization': 'Bearer ' + token(other)}
    assert api.post(root + '/reproduccion', headers=other_headers, json={'track_id': tid}).status_code == 403
    assert api.get('/youtube/feedback', headers=other_headers).json() == []
    assert db.sesiones.count_documents({}) == 0
