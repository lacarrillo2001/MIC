"""Compatibilidad experimental; no mide atención, emoción ni espectro de audio."""
import math


FEATURES = ("tempo", "energy", "valence", "danceability", "acousticness", "instrumentalness", "loudness")


def musical_id(song):
    if song.get("id") and song.get("idros") and song["id"] != song["idros"]:
        return None
    return song.get("id") or song.get("idros")


def number(song, key):
    value = song.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if key in {"energy", "valence", "danceability", "acousticness", "instrumentalness"} and not 0 <= value <= 1:
        return None
    if key == "tempo" and value <= 0:
        return None
    return float(value)


def frequency_category(song):
    acoustic = number(song, "acousticness")
    energy, loudness = number(song, "energy"), number(song, "loudness")
    dance, instrumental = number(song, "danceability"), number(song, "instrumentalness")
    if acoustic is not None and acoustic > .6:
        return "Medios"
    # No afirmar una rama posterior si faltan los datos de una rama previa.
    if acoustic is None or energy is None or loudness is None:
        return None
    if energy > .8 and loudness > -5:
        return "Agudos"
    if dance is None or instrumental is None:
        return None
    if dance > .7 and instrumental < .2:
        return "Graves"
    return "Medios"


def rank(song, profile, genres, rules, evaluation=None):
    attributes = {key: number(song, key) for key in FEATURES}
    targets = dict(profile.get("afinidad_aprendida", {}))
    preferred_tempo = profile.get("tempo_preferido")
    if preferred_tempo:
        targets["tempo"] = rules["tempo_targets"][preferred_tempo]
    score, reasons = 100.0, []
    evidence = 0
    for key, target in targets.items():
        value = attributes.get(key)
        if value is not None and key in rules["weights"]:
            penalty = abs(target - value) * rules["weights"][key]
            score -= penalty
            evidence += 1
            reasons.append(f"Distancia en {key}: {abs(target - value):.3f}; ajuste {-penalty:.3f}")
    preferred_artists = set(profile.get("artistas_preferidos", []))
    artist_match = bool(preferred_artists.intersection(song.get("id_artists", [])))
    genre_matches = set(profile.get("generos_preferidos", [])).intersection(genres)
    bonuses = rules["bonuses"]
    if artist_match:
        score += bonuses["artist"]
        evidence += 1
        reasons.append("Artista declarado como preferido")
    if genre_matches:
        score += bonuses["genre"] + (len(genre_matches) - 1) * bonuses["extra_genre"]
        evidence += 1
        reasons.append("Géneros asociados al artista: " + ", ".join(sorted(genre_matches)))
    if artist_match and genre_matches:
        score += bonuses["both"]
    adjustment = 0.0
    category = None
    if evaluation:
        category = frequency_category(song)
        definitions = {x["tono_id"]: x for x in evaluation["configuracion_utilizada"]["tonos"]}
        for answer in evaluation["respuestas"]:
            if not answer["omitido"] and definitions[answer["tono_id"]]["categoria_experimental"] == category and answer.get("molestia") is not None and answer["molestia"] >= rules["discomfort_threshold"]:
                adjustment = -float(rules["frequency_penalty"])
                reasons.append("Penalización heurística por molestia declarada; no es espectro medido ni criterio clínico")
                break
    if not evidence:
        reasons.append("Sin evidencia de afinidad suficiente: selección de respaldo, no personalización demostrada")
    return {"track_id": str(musical_id(song)), "name": song.get("name"), "artists": song.get("artists", []),
            "atributos_utilizados": attributes, "puntaje_compatibilidad": round(score + adjustment, 4),
            "ajuste_frecuencial": adjustment, "categoria_frecuencial_inferida": category,
            "motivos": reasons, "criterios_con_evidencia": evidence}
