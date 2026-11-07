import re
import unicodedata


def words(value):
    value = unicodedata.normalize('NFKD', str(value)).lower()
    return set(re.findall(r'[a-z0-9]+', ''.join(c for c in value if not unicodedata.combining(c))))


def choose_video(song, entries):
    candidates = []
    title = words(song['name']) - {'the', 'a', 'feat', 'ft'}
    artist = words(song['artists'][0])
    versions = {'cover', 'remix', 'live', 'slowed', 'sped', 'nightcore', 'karaoke', 'boosted', 'mashup', '8d'}
    for entry in entries:
        if not entry or not re.fullmatch(r'[A-Za-z0-9_-]{11}', str(entry.get('id', ''))):
            continue
        actual = words(entry.get('title', ''))
        context = actual | words(entry.get('channel', '')) | words(entry.get('uploader', ''))
        duration = entry.get('duration')
        if not title or not title.issubset(actual) or not artist.issubset(context):
            continue
        if (actual & versions) - words(song['name']) or entry.get('is_live') or entry.get('age_limit', 0) > 0:
            continue
        if not isinstance(duration, (int, float)) or abs(duration * 1000 - song['duration_ms']) > max(8000, song['duration_ms'] * .05):
            continue
        candidates.append(entry)
    return min(candidates, key=lambda e: abs(e['duration'] * 1000 - song['duration_ms']), default=None)
