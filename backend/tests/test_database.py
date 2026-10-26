import sqlite3

import pytest

from backend.database.connection import APPLICATION_ID, Database


def test_connection_settings_and_identity(database):
    for _ in range(3):
        with database.connect() as connection:
            assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert connection.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 3


def test_unrelated_database_is_not_migrated(tmp_path):
    path = tmp_path / "synthetic-unrelated.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated(note TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('Synthetic')")
    with pytest.raises(ValueError):
        Database(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT note FROM unrelated").fetchone()[0] == "Synthetic"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0


def test_health_and_no_database_on_import(client):
    assert client.get("/api/health").json() == {"estado": "ok"}
    assert client.get("/missing").json() == {"error": "ruta no encontrada"}
