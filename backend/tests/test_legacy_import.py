import sqlite3
from pathlib import Path

import pytest

from backend.controllers.movement_controller import add_payment, delete
from backend.database.connection import Database
from backend.import_legacy import import_legacy
from backend.models.movement import PaymentCreate
from backend.services.errors import LedgerError


def legacy(path: Path):
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE clients(id INTEGER PRIMARY KEY, name TEXT, created_at TEXT);
        CREATE TABLE movements(id INTEGER PRIMARY KEY, client_id INTEGER, detalle TEXT,
            cant INTEGER, precio_unitario REAL, n_remito TEXT, fecha TEXT, debe REAL,
            haber REAL, saldo REAL, added_date TEXT);
        CREATE TABLE transactions(id INTEGER PRIMARY KEY, summary TEXT);
        INSERT INTO clients VALUES(4, 'Cuenta sintetica', '2020-01-01');
        INSERT INTO movements VALUES(7,4,'Prenda sintetica',3,NULL,NULL,'2020-01-02',
            100.25,0,98.75,'2026-01-01');
        INSERT INTO transactions VALUES(1, 'Resumen sintetico');
    """)
    connection.commit()
    return connection


def test_import_preserves_values_locks_history_and_captures_wal(tmp_path):
    source, destination, archive = (tmp_path / name for name in ("old.db", "new.db", "copy.db"))
    with legacy(source) as old:
        old.execute("PRAGMA journal_mode=WAL")
        old.execute("INSERT INTO movements VALUES(9,4,'Pago',NULL,NULL,'R',NULL,0,5,93.75,NULL)")
        old.commit()
        before = old.execute("SELECT * FROM movements ORDER BY id").fetchall()
        import_legacy(source, destination, archive)
        assert before == old.execute("SELECT * FROM movements ORDER BY id").fetchall()
    with Database(destination).connect() as new:
        rows = new.execute(
            "SELECT id,unit_price,debit,credit,balance,created_at FROM movements ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            (7, None, 100.25, 0.0, 98.75, None),
            (9, None, 0.0, 5.0, 93.75, None),
        ]
        with pytest.raises(sqlite3.IntegrityError):
            new.execute("DELETE FROM movements")
    with sqlite3.connect(archive) as copy:
        assert copy.execute("SELECT summary FROM transactions").fetchone()[0] == "Resumen sintetico"
    database = Database(destination)
    payment, replayed = add_payment(database, 4, "synthetic-after-import", PaymentCreate(haber=5))
    assert not replayed and payment.id > 9 and payment.saldo == 89
    delete(database, 4, payment.id, payment.revision)
    with pytest.raises(LedgerError) as deleted_retry:
        add_payment(database, 4, "synthetic-after-import", PaymentCreate(haber=5))
    assert deleted_retry.value.status == 410
    with database.connect() as connection:
        assert connection.execute("SELECT balance FROM movements WHERE id=9").fetchone()[0] == 93.75
    with pytest.raises(ValueError):
        import_legacy(source, destination, tmp_path / "other.db")


def test_import_accepts_legacy_clients_without_creation_timestamp(tmp_path):
    source, destination, archive = (tmp_path / name for name in ("old.db", "new.db", "copy.db"))
    with legacy(source) as old:
        old.execute("ALTER TABLE clients DROP COLUMN created_at")
    import_legacy(source, destination, archive)
    with Database(destination).connect() as new:
        assert new.execute("SELECT created_at FROM clients").fetchone()[0] == ""


def test_import_failure_never_publishes_partial_database(tmp_path):
    source, destination, archive = (tmp_path / name for name in ("old.db", "new.db", "copy.db"))
    with legacy(source) as old:
        old.execute("UPDATE movements SET client_id=999")
    with pytest.raises(sqlite3.IntegrityError):
        import_legacy(source, destination, archive)
    assert not destination.exists()
    assert archive.exists()
