import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from backend.controllers import movement_controller
from backend.database import connection as storage
from backend.database.connection import Database
from backend.models.movement import DeliveryCreate

# Generated from the original Go JSON encoder using synthetic data only.
LEGACY_HASH = "3bf8aa3a03fef0bf2d9eec68e1d912d6c95e8a35cf30358468b656c26a550e0b"


def legacy_database(path: Path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            (storage.MIGRATIONS / "001_initial.sql").read_text(encoding="utf-8")
        )
        connection.execute("INSERT INTO clients(name) VALUES ('Cuenta sintética')")
        connection.execute("""INSERT INTO movements
        (client_id,origin,kind,description,quantity,unit_price,debit,credit,balance)
        VALUES (1,'imported','historical','Sintético',3,1000.25,17.75,0,-7.5)""")
        connection.execute(
            """INSERT INTO movements
        (client_id,origin,kind,description,quantity,unit_price,reference,business_date,
        created_at,debit,credit,balance,request_key,request_hash)
        VALUES (1,'native','delivery',?,2,1001,'R-001','2026-10-25',
        '2026-10-25T00:00:00Z',2002,0,1995,'legacy',?)""",
            ("Prenda sintética <A> & B\u2028C", LEGACY_HASH),
        )
        return connection.execute("SELECT * FROM movements ORDER BY id").fetchall()


def test_v1_upgrade_preserves_values_types_and_go_retry_hash(tmp_path):
    path = tmp_path / "synthetic-legacy.db"
    before = legacy_database(path)
    database = Database(path)
    database.initialize()
    with database.connect() as connection:
        after = connection.execute("SELECT * FROM movements ORDER BY id").fetchall()
        assert [tuple(row)[: len(before[0])] for row in after] == before
    input = DeliveryCreate(
        detalle="Prenda sintética <A> & B\u2028C",
        cant=2,
        precio_unitario=Decimal("1000.5"),
        n_remito="R-001",
        fecha="2026-10-25",
    )
    saved, replay = movement_controller.add_delivery(database, 1, "legacy", input)
    assert replay and saved.id == 2 and saved.saldo == 1995
    assert saved.revision == 1
    database.initialize()
    assert len(movement_controller.get_movements(database, 1)) == 2


def test_failed_migration_is_atomic(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-failed-upgrade.db"
    before = legacy_database(path)
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_initial.sql").write_text("-- not applied\n", encoding="utf-8")
    (migrations / "002_invalid.sql").write_text(
        "ALTER TABLE movements ADD COLUMN test_column TEXT;\n"
        "SELECT nonexistent_function();\nPRAGMA user_version=2;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(storage, "MIGRATIONS", migrations)
    with pytest.raises(sqlite3.OperationalError):
        Database(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT * FROM movements ORDER BY id").fetchall() == before


def test_future_version_rejected_without_changes(database):
    with database.connect() as connection:
        connection.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError):
        database.initialize()
    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 999
