"""Preselección probabilística; las correcciones son personales, no certificaciones."""


def voice_eligibility(preference, limits, reported):
    if preference == 'instrumental':
        return {'$and': [{'instrumentalness': {'$gte': limits['instrumental_min'], '$lte': 1}},
                         {'id': {'$nin': reported}}, {'idros': {'$nin': reported}}]}
    if preference == 'con_voz':
        return {'$or': [{'instrumentalness': {'$gte': 0, '$lte': limits['vocal_max']}},
                        {'id': {'$in': reported}}, {'idros': {'$in': reported}}]}
    return None


def voice_label(song, reported, limits):
    if song['track_id'] in reported:
        return 'Voz reportada por ti; letra sin verificar'
    value = song['atributos_utilizados'].get('instrumentalness')
    if value is None:
        return 'Presencia de voz desconocida'
    if value >= limits['instrumental_min']:
        return 'Probablemente instrumental; voz sin verificar'
    if value <= limits['vocal_max']:
        return 'Baja instrumentalidad; voz y letra sin verificar'
    return 'Presencia de voz sin verificar'
