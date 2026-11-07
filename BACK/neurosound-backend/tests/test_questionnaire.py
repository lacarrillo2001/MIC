from recomendacion.questionnaire import rank_questionnaire, session_profile
from shared.runtime import config


def test_opposite_preferences_and_missing_values():
    rules = config('recomendacion-web-v3')
    calm = {'id': 'calm', 'id_artists': ['a'], 'instrumentalness': .98, 'tempo': 70, 'energy': .2}
    lively = {'id': 'lively', 'id_artists': ['a'], 'instrumentalness': .01, 'tempo': 150, 'energy': .8}
    base = {'artistas_preferidos': ['a'], 'generos_preferidos': ['ambient'], 'afinidad_aprendida': {'energy': .9}}
    quiet = session_profile(dict(base, preferencia_voz='instrumental', tempo_preferido='lento'), 'suave', rules)
    energetic = session_profile(dict(base, preferencia_voz='con_voz', tempo_preferido='rapido'), 'energica', rules)
    rank = lambda song, profile: rank_questionnaire(song, profile, {'ambient'}, rules)
    assert rank(calm, quiet)['puntaje_compatibilidad'] > rank(lively, quiet)['puntaje_compatibilidad']
    assert rank(lively, energetic)['puntaje_compatibilidad'] > rank(calm, energetic)['puntaje_compatibilidad']
    assert rank(calm, quiet)['desglose_puntaje']['gustos']['aporte_puntos'] == 40
    assert base['afinidad_aprendida']['energy'] == .9
    missing = rank({'id': 'missing', 'id_artists': ['a']}, quiet)
    assert missing['puntaje_compatibilidad'] == 40
    assert missing['desglose_puntaje']['tempo']['coincidencia'] is None
    assert rank(calm, {})['puntaje_compatibilidad'] == 0
    assert rank(calm, {'preferencia_voz': 'instrumental'})['desglose_puntaje']['voz']['peso_aplicado'] == 1


def test_profile_to_list_snapshot_validation_and_session_override(system, student):
    clients, db, _ = system
    headers, uid = student
    users, api = clients['usuarios'], clients['recomendacion']
    db.artists.insert_one({'id': 'a', 'name': 'Example Artist', 'genres': ['ambient']})
    db.songsV2.insert_many([
        {'id': str(i), 'name': f'Track {i}', 'id_artists': ['a'], 'artists': ['Example Artist'],
         'instrumentalness': .9, 'tempo': 75, 'energy': .2, 'duration_ms': 180000} for i in range(5)])
    original = users.get('/perfiles/me', headers=headers).json()
    payload = {'version_esperada': original['version'], 'artistas_preferidos': ['a'],
               'generos_preferidos': ['ambiental'], 'preferencia_voz': 'instrumental', 'tempo_preferido': 'lento'}
    saved = users.put('/perfiles/me', headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()['preferencia_voz'] == 'instrumental'
    body = {'solicitud_id': 'questionnaire-list', 'modo': 'audio', 'actividad': 'lectura_comprensiva', 'energia_sesion': 'suave'}
    result = api.post('/youtube/recomendaciones', headers=headers, json=body)
    assert result.status_code == 201, result.text
    rec = result.json()
    assert rec['reglas_version'] == 'encuesta-web-v4'
    assert rec['contexto_sesion']['actividad'] == 'lectura_comprensiva'
    assert rec['perfil_utilizado']['afinidad_aprendida']['energy'] == .25
    assert users.get('/perfiles/me', headers=headers).json() == saved.json()
    assert all(x['puntaje_compatibilidad'] > 95 for x in rec['canciones'])
    assert api.post('/youtube/recomendaciones', headers=headers, json=body).json()['_id'] == rec['_id']
    assert api.post('/youtube/recomendaciones', headers=headers, json={**body, 'energia_sesion': 'energica'}).status_code == 409
    assert api.post('/youtube/recomendaciones', headers=headers, json={**body, 'actividad': 'invalid'}).status_code == 422
    assert users.put('/perfiles/me', headers=headers, json={**payload, 'generos_preferidos': ['a','b','c','d']}).status_code == 422
    assert api.get('/catalogo/artistas?q=example', headers=headers).json()[0]['id'] == 'a'
    assert api.get('/catalogo/artistas?q=%5B', headers=headers).status_code == 200
