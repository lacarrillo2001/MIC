import sys
from contextlib import ExitStack
from pathlib import Path

import mongomock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usuarios.app import build_app as users_app
from recomendacion.app import build_app as recommendation_app
from sesiones.app import build_app as sessions_app


@pytest.fixture
def system(monkeypatch, tmp_path):
    for key in ("JWT_SECRET", "USUARIOS_SERVICE_KEY", "RECOMENDACION_SERVICE_KEY", "SESIONES_SERVICE_KEY"):
        monkeypatch.setenv(key, "testing-" + key + "-" * 40)
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    db = mongomock.MongoClient(tz_aware=True).neurosound
    # mongomock no implementa check_exists=False; Mongo real sí se prueba con Docker.
    original_create = type(db).create_collection
    def mock_create(self, name, **kwargs):
        kwargs.pop("check_exists", None)
        return original_create(self, name, **kwargs)
    monkeypatch.setattr(type(db), "create_collection", mock_create)
    clients = {}

    def dispatch(caller):
        def call(target, method, path, body):
            response = clients[target].request(method, path, json=body,
                headers={"X-Service-Name": caller, "X-Service-Key": "testing-" + caller.upper() + "_SERVICE_KEY" + "-" * 40})
            if response.is_error:
                raise HTTPException(response.status_code, response.json()["detail"])
            return response.json()
        return call

    with ExitStack() as stack:
        for name, factory in (("usuarios", users_app), ("recomendacion", recommendation_app), ("sesiones", sessions_app)):
            clients[name] = stack.enter_context(TestClient(factory(db, dispatch(name))))
        yield clients, db, tmp_path


@pytest.fixture
def student(system):
    clients, db, path = system
    users = clients["usuarios"]
    registration = {"email": "Student@example.test", "password": "long-password-12345", "mayor_edad_confirmado": True,
                    "consentimiento_aceptado": True, "consentimiento_version": "consentimiento-v1"}
    result = users.post("/auth/registro", json=registration)
    assert result.status_code == 201, result.text
    login = users.post("/auth/login", json={"email": registration["email"], "password": registration["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": "Bearer " + login.json()["access_token"]}, result.json()["usuario_id"]
