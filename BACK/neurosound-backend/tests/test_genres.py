import pytest
from bson import ObjectId

from shared.genres import profile_genres, resolve_genres, suggestions
from recomendacion.engine import rank
from shared.runtime import config


@pytest.mark.parametrize('input_label,expected', [
    ('ambiental', 'ambient'), ('Música Ambiental', 'ambient'), ('CLÁSICA', 'classical'),
    (' electrónica ', 'electronica'), ('pop latino', 'latin pop'), ('ruido blanco', 'white noise'),
    ('Hip-Hop', 'hip hop'), ('lofi', 'lo-fi'), ('reguetón', 'reggaeton'), ('r & b', 'r&b'),
    ('rock alternativo', 'alternative rock'), ('jazz latino', 'latin jazz'),
])
def test_translation_uses_existing_catalogue_labels(system, input_label, expected):
    _, db, _ = system
    db.artists.insert_one({'id': 'a', 'genres': [expected]})
    assert resolve_genres(db, [input_label])['generos'] == [expected]


def test_unknown_not_guessed_and_exact_labels_preserved(system):
    _, db, _ = system
    db.artists.insert_one({'id': 'a', 'genres': ['ambient', 'lo-fi', 'cumbia pop', 'r&b']})
    result = resolve_genres(db, ['Ambiental', 'ambient', 'CUMBIA POP', 'lo-fi', 'r&b', 'instrumental', 'clasica'])
    assert result['generos'] == ['ambient', 'cumbia pop', 'lo-fi', 'r&b']
    assert result['no_reconocidos'] == ['instrumental', 'clasica']  # No hay classical en esta base.
    assert suggestions(db, 'ambiental')[0] == {'id': 'ambient', 'nombre': 'Ambiental'}


def test_profile_save_validation_and_old_profile_recommendation(system, student, monkeypatch):
    clients, db, _ = system
    headers, uid = student
    db.artists.insert_one({'id': 'ambient-artist', 'name': 'Artist', 'genres': ['ambient', 'classical']})
    db.songsV2.insert_one({'id': 'ambient-track', 'name': 'Song', 'artists': ['Artist'], 'id_artists': ['ambient-artist'], 'tempo': 95, 'duration_ms': 180000})
    users, api = clients['usuarios'], clients['recomendacion']
    profile = users.get('/perfiles/me', headers=headers).json()
    body = {'version_esperada': profile['version'], 'artistas_preferidos': [], 'generos_preferidos': ['ambiental', 'CLÁSICA'], 'tempo_preferido': 'moderado'}
    saved = users.put('/perfiles/me', headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()['generos_preferidos'] == ['ambient', 'classical']
    invalid = users.put('/perfiles/me', headers=headers, json={**body, 'version_esperada': saved.json()['version'], 'generos_preferidos': ['inventado']})
    assert invalid.status_code == 422 and 'inventado' in invalid.json()['detail']
    assert users.get('/perfiles/me', headers=headers).json()['version'] == saved.json()['version']
    # Perfil legado: se interpreta al recomendar, sin migrarlo ni cambiar su versión.
    db.perfiles.update_one({'usuario_id': ObjectId(uid)}, {'$set': {'generos_preferidos': ['ambiental', 'desconocido']}})
    original = db.perfiles.find_one({'usuario_id': ObjectId(uid)})
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-private-key')
    result = api.post('/youtube/recomendaciones', headers=headers, json={'solicitud_id': 'genre-translation-test', 'limite': 5})
    assert result.status_code == 201, result.text
    rec = result.json()
    assert rec['perfil_utilizado']['generos_preferidos'] == ['ambient']
    assert rec['normalizacion_generos']['no_reconocidos'] == ['desconocido']
    assert rec['canciones'][0]['puntaje_compatibilidad'] == 100
    assert set(rec['canciones'][0]['desglose_puntaje']) == {'gustos', 'tempo'}
    assert db.perfiles.find_one({'usuario_id': ObjectId(uid)}) == original
    options = api.get('/catalogo/generos?q=clásica', headers=headers)
    assert options.status_code == 200 and options.json()[0]['id'] == 'classical'
    assert api.post('/internal/generos/resolver', headers=headers, json={'generos': ['ambiental']}).status_code == 403
