from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.database.connection import Database
from backend.main import create_app


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "synthetic ledger #1 %.db")
    database.initialize()
    return database


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(
        create_app(tmp_path / "synthetic-api.db", origin="https://localhost:8443"),
        base_url="https://localhost:8443",
        headers={"Origin": "https://localhost:8443"},
        raise_server_exceptions=False,
    ) as client:
        yield client
