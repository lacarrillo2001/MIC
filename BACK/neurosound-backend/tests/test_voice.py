import copy
from bson import ObjectId
from shared.runtime import token


def test_voice_prefilter_personal_correction_and_withdrawal(system, student):
    clients, db, _ = system
    headers, uid = student
    users, api = clients['usuarios'], clients['recomendacion']
    db.songsV2.insert_many([{'id': tid, 'name': tid, 'artists': ['Artist'], 'id_artists': ['artist'],
        'duration_ms': 180000, 'instrumentalness': val, 'tempo': 90, 'energy': .3}
        for tid, val in [('instrumental', .95), ('vocal', .05), ('uncertain', .5)]])
    db.songsV2.insert_one({'id': 'missing', 'name': 'Missing', 'duration_ms': 180000})
    def profile(voice):
        p = users.get('/perfiles/me', headers=headers).json()
        response = users.put('/perfiles/me', headers=headers, json={'version_esperada': p['version'], 'preferencia_voz': voice})
        assert response.status_code == 200, response.text
        return response.json()
    def make(key):
        response = api.post('/youtube/recomendaciones', headers=headers,
                            json={'solicitud_id': key, 'modo': 'audio', 'limite': 5})
        assert response.status_code == 201, response.text
        return response.json()
    saved = profile('instrumental')
    rec = make('voice-instrumental')
    assert [s['track_id'] for s in rec['canciones']] == ['instrumental']
    assert rec['aviso_seleccion'] and not rec['preseleccion_voz']['verificacion_audio']
    root = f"/youtube/recomendaciones/{rec['_id']}"
    report = {'track_id': 'instrumental', 'tiene_voz': True, 'revision': 0}
    assert api.post(root + '/voz', headers=headers, json=report).status_code == 409
    api.post(root + '/reproduccion', headers=headers, json={'track_id': 'instrumental'})
    old_profile = copy.deepcopy(db.perfiles.find_one({'usuario_id': ObjectId(uid)}))
    first = api.post(root + '/voz', headers=headers, json=report)
    assert first.status_code == 200, first.text
    assert api.post(root + '/voz', headers=headers, json=report).json()['revision'] == 1
    assert db.feedback.count_documents({'tipo': 'voz_web'}) == 1
    assert db.feedback.count_documents({'tipo': 'youtube_web'}) == 0
    assert db.perfiles.find_one({'usuario_id': ObjectId(uid)}) == old_profile
    assert api.get(root + '/voz?track_id=instrumental', headers=headers).json() == {'tiene_voz': True, 'revision': 1}
    assert api.get('/youtube/feedback', headers=headers).json() == []
    assert len(api.get('/youtube/voz', headers=headers).json()) == 1
    assert api.get('/youtube/voz?pagina=0', headers=headers).status_code == 422
    assert api.post('/youtube/recomendaciones', headers=headers, json={'solicitud_id': 'voice-excluded', 'modo': 'audio'}).status_code == 409
    assert api.post(f"/feedback/{first.json()['_id']}/reintentar", headers=headers).status_code == 409
    assert api.post(root + '/voz', headers=headers, json={**report, 'tiene_voz': False}).status_code == 409
    correction = api.post(root + '/voz', headers=headers, json={**report, 'tiene_voz': False, 'revision': 1})
    assert correction.status_code == 200
    assert make('voice-restored')['canciones'][0]['track_id'] == 'instrumental'
    profile('con_voz')
    assert [s['track_id'] for s in make('voice-vocal-list')['canciones']] == ['vocal']
    profile(None)
    assert len(make('voice-no-preference')['canciones']) == 4
    other = db.usuarios.insert_one({'estado': 'activo', 'rol': 'estudiante', 'mayor_edad_confirmado': True,
                                    'consentimiento': {'aceptado': True, 'version': 'consentimiento-v1'}}).inserted_id
    foreign = {'Authorization': 'Bearer ' + token(other)}
    assert api.get(root + '/voz?track_id=instrumental', headers=foreign).status_code == 403
    assert api.post(root + '/voz', headers=foreign, json=report).status_code == 403
    assert api.get('/youtube/voz', headers=foreign).json() == []
