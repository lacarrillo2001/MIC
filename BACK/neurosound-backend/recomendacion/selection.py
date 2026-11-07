"""Selección acotada y diversidad; los pesos siguen siendo experimentales."""
import hashlib
import random
from collections import Counter

from recomendacion.engine import musical_id


def candidates(db, profile, rules, excluded=(), eligibility=None):
    limit = rules['candidate_limit']
    artists = profile.get('artistas_preferidos', [])
    genres = profile.get('generos_preferidos', [])
    pools = []

    def sample(query, size):
        if eligibility:
            query = {'$and': [query, eligibility]}
        if excluded:
            query = {'$and': [query, {'id': {'$nin': list(excluded)}}, {'idros': {'$nin': list(excluded)}}]}
        return list(db.songsV2.aggregate([{'$match': query}, {'$sample': {'size': size}}]))

    if artists:
        pools.append(sample({'id_artists': {'$in': artists}}, limit // 4))
    genre_ids = [a['id'] for a in db.artists.aggregate([
        {'$match': {'genres': {'$in': genres}}}, {'$sample': {'size': 1000}}, {'$project': {'id': 1}}]) if a.get('id')] if genres else []
    if genre_ids:
        pools.append(sample({'id_artists': {'$in': genre_ids}}, limit // 4))
    targets = dict(profile.get('afinidad_aprendida', {}))
    if profile.get('tempo_preferido'):
        targets['tempo'] = rules['tempo_targets'][profile['tempo_preferido']]
    conditions = []
    for key in ('tempo', 'energy', 'valence'):
        if key in targets:
            margin = 20 if key == 'tempo' else .15
            conditions.append({key: {'$gte': targets[key] - margin, '$lte': targets[key] + margin}})
    if profile.get('preferencia_voz'):
        conditions.append({'instrumentalness': {'$gte': .5} if profile['preferencia_voz'] == 'instrumental' else {'$lt': .5}})
    if conditions:
        pools.append(sample({'$and': conditions}, limit // 4))
    pools.append(sample({}, limit))
    result, seen = [], set()
    for pool in pools:
        for song in pool:
            tid = musical_id(song)
            if isinstance(tid, str) and tid and tid not in seen:
                seen.add(tid)
                result.append(song)
                if len(result) == limit:
                    return result
    return result


def diverse(ranked, limit, seed, recent=(), max_artist=2, band=5):
    """Aleatoriedad reproducible dentro de bandas de cinco puntos.

    Se relaja primero el historial y luego el límite por artista si faltan opciones.
    """
    rng = random.Random(hashlib.sha256(seed.encode()).hexdigest())
    ordered = sorted(ranked, key=lambda x: (-x['puntaje_compatibilidad'], x['track_id']))
    shuffled = []
    while ordered:
        top = ordered[0]['puntaje_compatibilidad']
        group = []
        while ordered and top - ordered[0]['puntaje_compatibilidad'] <= band:
            group.append(ordered.pop(0))
        rng.shuffle(group)
        shuffled.extend(group)
    selected, used, counts = [], set(), Counter()
    for avoid_recent, cap in ((True, True), (False, True), (False, False)):
        for song in shuffled:
            tid = song['track_id']
            artists = song.get('id_artists') or song.get('artists') or [tid]
            if tid in used or (avoid_recent and tid in recent) or (cap and any(counts[a] >= max_artist for a in artists)):
                continue
            selected.append(song)
            used.add(tid)
            counts.update(set(artists))
            if len(selected) == limit:
                return selected
    return selected


def web_profile(db, uid, profile, rate):
    """Reconstruye afinidad web desde respuestas vigentes: corregir no acumula ajustes.

    Conserva intacta la afinidad del perfil utilizada por sesiones VR.
    """
    profile = {**profile, 'afinidad_aprendida': dict(profile.get('afinidad_aprendida', {}))}
    feedback = list(db.feedback.find({'usuario_id': uid, 'tipo': 'youtube_web'}).sort([('creado_en', 1), ('_id', 1)]))
    excluded = set()
    for item in feedback:
        if item['respuesta'] in ('no_me_gusta', 'molestia'):
            excluded.add(item['track_id'])
        elif item['respuesta'] == 'me_gusta':
            for key in ('energy', 'valence'):
                value = item['atributos_utilizados'].get(key)
                if value is not None:
                    old = profile['afinidad_aprendida'].get(key)
                    profile['afinidad_aprendida'][key] = value if old is None else old + rate * (value - old)
    return profile, excluded
