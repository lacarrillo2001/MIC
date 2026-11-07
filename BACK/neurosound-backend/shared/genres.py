"""Equivalencias explícitas: conservan las etiquetas reales del catálogo."""
import re
import unicodedata

from shared.runtime import config


def normalized(value):
    value = unicodedata.normalize('NFKD', value.strip().lower())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', value.replace('-', ' ')).strip()


def resolve_genres(db, values):
    available = set(db.artists.distinct('genres'))
    by_key = {}
    for label in available:
        by_key.setdefault(normalized(label), set()).add(label)
    aliases = config('generos-v1')['equivalencias']
    resolved, unknown, changes = set(), [], []
    for value in values:
        value = value.strip()
        key = normalized(value)
        # Una etiqueta exacta del catálogo siempre tiene prioridad.
        matches = {value} if value in available else by_key.get(key, set())
        if not matches:
            target = aliases.get(key)
            matches = {target} if target in available else set()
        if len(matches) != 1:
            unknown.append(value)
            continue
        label = next(iter(matches))
        resolved.add(label)
        if value != label:
            changes.append({'entrada': value, 'catalogo': label})
    return {'generos': sorted(resolved), 'no_reconocidos': unknown, 'equivalencias_aplicadas': changes}


def profile_genres(db, profile):
    result = resolve_genres(db, profile.get('generos_preferidos', []))
    return {**profile, 'generos_preferidos': result['generos']}, result


def suggestions(db, query='', limit=30):
    available = sorted(db.artists.distinct('genres'))
    settings = config('generos-v1')
    key = normalized(query)
    aliases = settings['equivalencias']
    preferred = set(settings['etiquetas_es'])
    rows = []
    for label in available:
        translated = settings['etiquetas_es'].get(label, label)
        terms = [normalized(label), normalized(translated)] + [a for a, target in aliases.items() if target == label]
        if key and not any(key in term for term in terms):
            continue
        rows.append({'id': label, 'nombre': translated})
    rows.sort(key=lambda r: (0 if key and (normalized(r['id']) == key or aliases.get(key) == r['id']) else 1,
                             0 if r['id'] in preferred else 1, r['id']))
    return rows[:limit]
