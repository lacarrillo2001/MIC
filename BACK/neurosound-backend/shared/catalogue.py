"""Carga incremental del catálogo: conserva documentos y tipos Extended JSON."""
import hashlib
import json
import os
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

from bson import ObjectId, json_util
from pymongo.errors import BulkWriteError


def documents(filename):
    """Lee JSON array o JSON Lines sin cargar el archivo completo en memoria."""
    decoder = json.JSONDecoder(object_hook=json_util.object_hook)
    with Path(filename).open(encoding="utf-8-sig") as stream:
        buffer, position, eof = "", 0, False

        def fill():
            nonlocal buffer, position, eof
            buffer = buffer[position:]
            position = 0
            block = stream.read(65536)
            buffer += block
            eof = not block

        def peek():
            nonlocal position
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer):
                    return buffer[position]
                if eof:
                    return ""
                fill()

        def value():
            nonlocal position
            while True:
                try:
                    item, end = decoder.raw_decode(buffer, position)
                    position = end
                    return item
                except json.JSONDecodeError as exc:
                    if eof:
                        raise ValueError("JSON incompleto o inválido") from exc
                    if len(buffer) - position > 8 * 1024 * 1024:
                        raise ValueError("Documento mayor de 8 MiB o JSON inválido")
                    fill()

        first = peek()
        if not first:
            raise ValueError("Archivo vacío")
        array = first == "["
        if array:
            position += 1
            if peek() == "]":
                position += 1
                if peek():
                    raise ValueError("Contenido después del array")
                return
        while True:
            peek()
            item = value()
            if not isinstance(item, dict):
                raise ValueError("Cada registro debe ser un objeto JSON")
            yield item
            delimiter = peek()
            if not array:
                if not delimiter:
                    return
            elif delimiter == "]":
                position += 1
                if peek():
                    raise ValueError("Contenido después del array")
                return
            elif delimiter == ",":
                position += 1
                if peek() == "]":
                    raise ValueError("Coma final no permitida")
            else:
                raise ValueError("Falta coma o cierre del array")


def identifier(item, collection):
    return item.get("id") or (item.get("idros") if collection == "songsV2" else None)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def equivalent(left, right):
    """Mongo representa Date como UTC; naive en Extended JSON también significa UTC.

    Solo normaliza para COMPARAR. No cambia los documentos ni sus valores.
    """
    def comparable(value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        if isinstance(value, dict):
            return {k: comparable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [comparable(v) for v in value]
        return value
    return comparable({k: v for k, v in left.items() if k != "_id"}) == comparable({k: v for k, v in right.items() if k != "_id"})


def preflight(path, collection):
    if collection not in {"artists", "songsV2"}:
        raise ValueError("Colección no permitida")
    before = file_hash(path)
    ids, mongo_ids = set(), set()
    count = 0
    for item in documents(path):
        key = identifier(item, collection)
        if not isinstance(key, str) or not key:
            raise ValueError("Cada registro requiere id (o idros en songsV2) string")
        if key in ids:
            raise ValueError(f"Identificador musical duplicado dentro de {collection}")
        ids.add(key)
        if "_id" in item:
            if not isinstance(item["_id"], (str, ObjectId)):
                raise ValueError("_id debe ser ObjectId o string")
            if item["_id"] in mongo_ids:
                raise ValueError("_id duplicado dentro del archivo")
            mongo_ids.add(item["_id"])
        fields = ("artists", "id_artists") if collection == "songsV2" else ("genres",)
        for field in fields:
            if field in item and (not isinstance(item[field], list) or not all(isinstance(x, str) for x in item[field])):
                raise ValueError(f"{field} debe ser un array de strings")
        if collection == "songsV2" and item.get("id") and item.get("idros") and item["id"] != item["idros"]:
            raise ValueError("id e idros distintos en el mismo registro")
        count += 1
    if before != file_hash(path):
        raise ValueError("El archivo cambió durante la validación")
    return {"documentos": count, "sha256": before}


def load_file(db, path, collection, validation=None, batch_size=1000):
    validation = validation or preflight(path, collection)
    if file_hash(path) != validation["sha256"]:
        raise ValueError("El archivo cambió después de validarse")
    counters = {"insertados": 0, "identicos": 0, "conflictos_conservados": 0, "colisiones_concurrentes": 0}
    stream = iter(documents(path))
    processed = 0
    while batch := list(islice(stream, batch_size)):
        keys = [identifier(x, collection) for x in batch]
        mongo_ids = [x["_id"] for x in batch if "_id" in x]
        clauses = [{"id": {"$in": keys}}, {"_id": {"$in": mongo_ids}}]
        if collection == "songsV2":
            clauses.append({"idros": {"$in": keys}})
        existing = list(db[collection].find({"$or": clauses}))
        by_key, by_id = {}, {}
        for item in existing:
            by_id[item["_id"]] = item
            fields = ("id", "idros") if collection == "songsV2" else ("id",)
            for key in {item[field] for field in fields if isinstance(item.get(field), str)}:
                by_key.setdefault(key, []).append(item)
        pending = []
        for item in batch:
            key = identifier(item, collection)
            matches = by_key.get(key, [])
            by_mongo_id = by_id.get(item.get("_id"))
            if by_mongo_id is not None and all(x["_id"] != by_mongo_id["_id"] for x in matches):
                matches = [*matches, by_mongo_id]
            if matches:
                same = len(matches) == 1 and equivalent(matches[0], item)
                counters["identicos" if same else "conflictos_conservados"] += 1
            else:
                if "_id" not in item:
                    # Estable incluso si se repite una importación concurrente.
                    item["_id"] = ObjectId(hashlib.sha256((collection + ":" + key).encode()).hexdigest()[:24])
                pending.append(item)
        if pending:
            try:
                db[collection].insert_many(pending, ordered=False)
                counters["insertados"] += len(pending)
            except BulkWriteError as exc:
                errors = exc.details.get("writeErrors", [])
                if exc.details.get("writeConcernErrors") or any(x["code"] != 11000 for x in errors):
                    raise
                counters["insertados"] += exc.details.get("nInserted", 0)
                counters["colisiones_concurrentes"] += len(errors)
        processed += len(batch)
        if processed % 25000 == 0:
            print(f"Catálogo {collection}: {processed}/{validation['documentos']} comprobados", flush=True)
    if file_hash(path) != validation["sha256"]:
        raise ValueError("El archivo cambió durante la carga; revisar y reenviar. No se borraron registros")
    result = {"coleccion": collection, **validation, **counters, "total_en_mongo": db[collection].count_documents({})}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def auto_import(db):
    root = Path("/imports").resolve()
    paths = {"artists": Path(os.environ.get("CATALOGUE_ARTISTS_FILE", "/imports/artists.json")).resolve(),
             "songsV2": Path(os.environ.get("CATALOGUE_SONGS_FILE", "/imports/songsV2.json")).resolve()}
    for path in paths.values():
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Falta un JSON del catálogo dentro de /imports. Revisar README antes de iniciar")
    # Se validan AMBOS archivos antes de insertar el primer registro.
    validations = {name: preflight(path, name) for name, path in paths.items()}
    return [load_file(db, path, name, validations[name]) for name, path in paths.items()]
