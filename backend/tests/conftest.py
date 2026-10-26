from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.database.connection import Database
from backend.main import create_app
from backend.services.passwords import create_credential


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "synthetic ledger #1 %.db")
    database.initialize()
    return database


@pytest.fixture(scope="session")
def synthetic_password():
    return "Contraseña sintética de pruebas 42"


@pytest.fixture(scope="session")
def credential(synthetic_password):
    return create_credential(synthetic_password)


@pytest.fixture
def anonymous_client(tmp_path: Path, credential):
    with TestClient(
        create_app(
            tmp_path / "synthetic-api.db", origin="https://localhost:8443", credential=credential
        ),
        base_url="https://localhost:8443",
        headers={"Origin": "https://localhost:8443"},
        raise_server_exceptions=False,
    ) as client:
        yield client


@pytest.fixture
def client(anonymous_client, synthetic_password):
    response = anonymous_client.post("/api/auth/login", json={"password": synthetic_password})
    assert response.status_code == 200
    return anonymous_client
