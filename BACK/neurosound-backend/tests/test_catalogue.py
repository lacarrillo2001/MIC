import json

import mongomock
import pytest
from bson import ObjectId

from shared.catalogue import documents, load_file, preflight


def write_file(tmp_path, items):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def test_streaming_extended_json_and_boundary(tmp_path):
    path = write_file(tmp_path, [{"_id": {"$oid": "111111111111111111111111"}, "id": "first", "name": "x" * 70000}, {"id": "second"}])
    data = list(documents(path))
    assert data[0]["_id"] == ObjectId("111111111111111111111111")
    assert data[1]["id"] == "second"
    assert len(data[0]["name"]) == 70000


def test_json_lines_and_bom(tmp_path):
    path = tmp_path / "lines.json"
    path.write_text('\ufeff  {"id":"a"}\n {"id":"b"}\n', encoding="utf-8")
    assert [x["id"] for x in documents(path)] == ["a", "b"]


@pytest.mark.parametrize("content", ["", "[{}", "[{},]", "[{} {}]", "[]bad", "[null]"])
def test_invalid_json_rejected(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        list(documents(path))


def test_idempotent_import_preserves_unknown_and_non_numeric_fields(tmp_path):
    path = write_file(tmp_path, [{"id": "one", "artists": ["A"], "id_artists": ["a"], "energy": "", "extra": {"original": True}}, {"idros": "two", "artists": [], "id_artists": []}])
    db = mongomock.MongoClient().test
    result = load_file(db, path, "songsV2", batch_size=1)
    assert result["insertados"] == 2
    before = list(db.songsV2.find())
    result = load_file(db, path, "songsV2", batch_size=1)
    assert result["insertados"] == 0 and result["identicos"] == 2
    assert list(db.songsV2.find()) == before
    assert before[0]["energy"] == "" and before[0]["extra"]["original"]


def test_conflicts_not_overwritten_and_new_records_inserted(tmp_path):
    db = mongomock.MongoClient().test
    old_id = db.artists.insert_one({"id": "one", "name": "Usuario original", "genres": ["original"]}).inserted_id
    path = write_file(tmp_path, [{"id": "one", "name": "Fuente distinta", "genres": []}, {"id": "two", "genres": []}])
    result = load_file(db, path, "artists")
    assert result["conflictos_conservados"] == 1
    assert result["insertados"] == 1
    assert db.artists.find_one({"_id": old_id})["name"] == "Usuario original"


def test_preflight_entire_file_before_insertion(tmp_path):
    db = mongomock.MongoClient().test
    path = write_file(tmp_path, [{"id": "one", "genres": []}, {"id": "two", "genres": "not an array"}])
    with pytest.raises(ValueError):
        load_file(db, path, "artists")
    assert db.artists.count_documents({}) == 0


def test_preflight_duplicate_ids_and_changed_source(tmp_path):
    path = write_file(tmp_path, [{"id": "one"}, {"id": "one"}])
    with pytest.raises(ValueError):
        preflight(path, "songsV2")
    path = write_file(tmp_path, [{"id": "one"}])
    validation = preflight(path, "songsV2")
    path.write_text('[{"id":"two"}]', encoding="utf-8")
    with pytest.raises(ValueError):
        load_file(mongomock.MongoClient().test, path, "songsV2", validation)


def test_utc_dates_naive_vs_aware_not_false_conflicts(tmp_path):
    from datetime import datetime, timezone
    path = write_file(tmp_path, [{"id": "dated", "release_date": {"$date": {"$numberLong": "-1420156800000"}}, "artists": [], "id_artists": []}])
    db = mongomock.MongoClient(tz_aware=True).test
    assert load_file(db, path, "songsV2")["insertados"] == 1
    date_before = db.songsV2.find_one()["release_date"]
    assert date_before.tzinfo is not None
    result = load_file(db, path, "songsV2")
    assert result["identicos"] == 1 and result["conflictos_conservados"] == 0
    assert db.songsV2.find_one()["release_date"] == date_before
