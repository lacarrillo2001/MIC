"""Auditoría de solo lectura de listas web v3, sin credenciales ni datos personales en salida.

Ejecutar dentro del contenedor recomendacion mediante stdin.
"""
import json
import os
from pymongo import MongoClient

client = MongoClient(host=os.environ['MONGO_HOST'], username=os.environ['MONGO_USER'],
                     password=os.environ['MONGO_PASSWORD'], authSource=os.environ['MONGO_DATABASE'])
db = client[os.environ['MONGO_DATABASE']]
reports = []
for rec in db.recomendaciones.find({'tipo': 'youtube_web', 'reglas_version': 'encuesta-web-v3'}).sort('creado_en', -1).limit(3):
    p, rules = rec['perfil_utilizado'], rec['reglas_utilizadas']
    active = {}
    if p.get('artistas_preferidos') or p.get('generos_preferidos'):
        active['gustos'] = rules['weights']['gustos']
    if p.get('preferencia_voz'):
        active['voz'] = rules['weights']['voz']
    if p.get('tempo_preferido'):
        active['tempo'] = rules['weights']['tempo']
    if p.get('afinidad_aprendida', {}).get('energy') is not None:
        active['energy'] = rules['weights']['energy']
    total = sum(active.values())
    songs = []
    for row in rec['canciones']:
        original = db.songsV2.find_one({'$or': [{'id': row['track_id']}, {'idros': row['track_id']}]})
        artists = list(db.artists.find({'id': {'$in': original.get('id_artists', [])}})) if original else []
        genres = {g.lower() for a in artists for g in a.get('genres', [])}
        artist_match = bool(set(p.get('artistas_preferidos', [])).intersection(original.get('id_artists', []))) if original else False
        genre_match = sorted(set(p.get('generos_preferidos', [])).intersection(genres))
        attrs = row['atributos_utilizados']
        values = {'gustos': float(artist_match or bool(genre_match))}
        voice = attrs.get('instrumentalness')
        values['voz'] = voice if p.get('preferencia_voz') == 'instrumental' else None if voice is None else 1 - voice
        if p.get('tempo_preferido'):
            low, high = rules['tempo_ranges'][p['tempo_preferido']]
            tempo = attrs.get('tempo')
            values['tempo'] = None if tempo is None else max(0, 1 - max(low-tempo, 0, tempo-high) / rules['tempo_falloff_bpm'])
        target = p.get('afinidad_aprendida', {}).get('energy')
        energy = attrs.get('energy')
        values['energy'] = None if target is None or energy is None else max(0, 1 - abs(target-energy))
        contributions = {k: round(100 * w / total * (values[k] or 0), 4) for k, w in active.items()}
        expected = round(sum(contributions.values()), 4)
        songs.append({'track_id': row['track_id'], 'titulo': row['name'], 'artistas': row['artists'], 'tempo': attrs.get('tempo'),
                      'instrumentalness': voice, 'energy': energy, 'coincide_artista': artist_match,
                      'generos_coincidentes': genre_match, 'puntaje_guardado': row['puntaje_compatibilidad'],
                      'puntaje_recalculado': expected, 'coincide_calculo': abs(expected-row['puntaje_compatibilidad']) < .001,
                      'aportes': contributions,
                      'atributos_coinciden_catalogo': bool(original) and all(original.get(k) == v for k,v in attrs.items() if v is not None)})
    reports.append({'creada_en': rec['creado_en'].isoformat(), 'actividad': rec.get('contexto_sesion'),
                    'generos': p.get('generos_preferidos'), 'cantidad_artistas_preferidos': len(p.get('artistas_preferidos', [])),
                    'voz': p.get('preferencia_voz'), 'ritmo': p.get('tempo_preferido'),
                    'energia_objetivo': p.get('afinidad_aprendida', {}).get('energy'),
                    'pesos_activos': {k: round(v/total, 6) for k,v in active.items()}, 'canciones': songs})
print(json.dumps(reports, ensure_ascii=False, indent=2))
