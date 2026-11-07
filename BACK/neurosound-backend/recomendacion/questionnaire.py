"""Afinidad declarada: no estima concentración ni frecuencias acústicas."""
from recomendacion.engine import FEATURES, musical_id, number


def session_profile(profile, energy, rules):
    result = {**profile, 'afinidad_aprendida': dict(profile.get('afinidad_aprendida', {}))}
    result['energia_sesion'] = energy
    if energy in rules['energy_targets']:
        result['afinidad_aprendida']['energy'] = rules['energy_targets'][energy]
    return result


def rank_questionnaire(song, profile, genres, rules):
    attributes = {key: number(song, key) for key in FEATURES}
    parts = {}
    preferred_artists = set(profile.get('artistas_preferidos', []))
    preferred_genres = set(profile.get('generos_preferidos', []))
    artist_match = bool(preferred_artists.intersection(song.get('id_artists', [])))
    matches = sorted(preferred_genres.intersection(genres))
    if preferred_artists or preferred_genres:
        # Un solo componente: coincidir por dos vías no duplica el beneficio.
        parts['gustos'] = {'coincidencia': float(artist_match or bool(matches)),
                          'artista_preferido': artist_match, 'generos_coincidentes': matches}
    voice = profile.get('preferencia_voz')
    if voice:
        value = attributes['instrumentalness']
        parts['voz'] = {'coincidencia': None if value is None else value if voice == 'instrumental' else 1 - value,
                        'preferencia': voice, 'valor_catalogo': value}
    tempo = profile.get('tempo_preferido')
    if tempo:
        low, high = rules['tempo_ranges'][tempo]
        value = attributes['tempo']
        distance = None if value is None else max(low - value, 0, value - high)
        parts['tempo'] = {'coincidencia': None if distance is None else max(0, 1 - distance / rules['tempo_falloff_bpm']),
                          'rango_bpm': [low, high], 'valor_catalogo': value}
    target = profile.get('afinidad_aprendida', {}).get('energy')
    if target is not None:
        value = attributes['energy']
        parts['energy'] = {'coincidencia': None if value is None else max(0, 1 - abs(target - value)),
                          'objetivo': target, 'valor_catalogo': value,
                          'origen': 'sesion' if profile.get('energia_sesion') in rules['energy_targets'] else 'feedback_explicito'}
    total = sum(rules['weights'][key] for key in parts)
    score = 0
    for key, part in parts.items():
        part['peso_aplicado'] = rules['weights'][key] / total
        # Ausencia de atributos no recibe coincidencia perfecta ni cambia el denominador.
        part['aporte_puntos'] = round(100 * part['peso_aplicado'] * (part['coincidencia'] or 0), 4)
        score += part['aporte_puntos']
    evidence = sum(part['coincidencia'] is not None for part in parts.values())
    return {'track_id': str(musical_id(song)), 'name': song.get('name'), 'artists': song.get('artists', []),
            'atributos_utilizados': attributes, 'puntaje_compatibilidad': round(score, 4),
            'desglose_puntaje': parts, 'criterios_con_evidencia': evidence,
            'motivos': [f'{key}: {part["aporte_puntos"]:.2f} puntos' for key, part in parts.items()] or
                       ['Sin preferencias: selección diversa de respaldo'],
            'ajuste_frecuencial': 0, 'categoria_frecuencial_inferida': None}
