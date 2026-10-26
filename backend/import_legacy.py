"""Explicit, one-time legacy import into a new independent ledger.

The source is read-only. SQLite backup captures a consistent image including WAL.
No business values are printed or included in exception messages.
"""

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.database.connection import Database

SOURCE_COLUMNS = (
    "id, client_id, detalle, cant, precio_unitario, n_remito, fecha, debe, haber, saldo"
)
TARGET_COLUMNS = (
    "id, client_id, description, quantity, unit_price, reference, business_date, "
    "debit, credit, balance"
)


def import_legacy(source: Path, destination: Path, archive: Path) -> None:
    source, destination, archive = source.resolve(), destination.resolve(), archive.resolve()
    if not source.is_file() or destination.exists() or archive.exists():
        raise ValueError("se requiere origen existente y destinos nuevos")
    if len({source, destination, archive}) != 3:
        raise ValueError("las rutas deben ser distintas")
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    # Reserve exclusively; a pre-existing archive is never overwritten.
    with archive.open("xb"):
        pass
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as original:
        original.execute("PRAGMA query_only=ON")
        with closing(sqlite3.connect(archive)) as snapshot:
            original.backup(snapshot)
    with closing(sqlite3.connect(archive.as_uri() + "?mode=ro", uri=True)) as snapshot:
        snapshot.execute("PRAGMA query_only=ON")
        if snapshot.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("la copia no supera la validacion de integridad")
        if snapshot.execute("PRAGMA application_id").fetchone()[0] != 0:
            raise ValueError("el origen no corresponde al formato anterior")
        # Explicit projection also rejects unknown/incomplete source layouts.
        snapshot.execute(f"SELECT {SOURCE_COLUMNS}, added_date FROM movements LIMIT 0")
        snapshot.execute("SELECT id, name FROM clients LIMIT 0")
        client_fields = {row[1] for row in snapshot.execute("PRAGMA table_info(clients)")}
        client_created = "created_at" if "created_at" in client_fields else "NULL"
        with TemporaryDirectory(prefix="ledger-import-", dir=destination.parent) as folder:
            temporary = Path(folder) / "ledger.db"
            database = Database(temporary)
            database.initialize()
            with database.transaction() as target:
                for row in snapshot.execute(
                    f"SELECT id, name, {client_created} FROM clients ORDER BY id"
                ):
                    target.execute(
                        "INSERT INTO clients(id, name, created_at) VALUES (?, ?, ?)",
                        (row[0], row[1], row[2] or ""),
                    )
                for row in snapshot.execute(f"SELECT {SOURCE_COLUMNS} FROM movements ORDER BY id"):
                    # Historical added_date can be an import timestamp, not the
                    # original event time. Preserve it in the source archive only.
                    target.execute(
                        f"INSERT INTO movements({TARGET_COLUMNS}, origin, kind) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported', 'historical')",
                        row,
                    )
                # Compare every mapped value and SQLite storage class without rounding.
                for source_table, source_columns, target_columns in (
                    ("clients", "id, name", "id, name"),
                    ("movements", SOURCE_COLUMNS, TARGET_COLUMNS),
                ):
                    old = snapshot.execute(
                        f"SELECT {source_columns} FROM {source_table} ORDER BY id"
                    )
                    new = target.execute(f"SELECT {target_columns} FROM {source_table} ORDER BY id")
                    for before, after in zip(old, new, strict=True):
                        if tuple(before) != tuple(after) or any(
                            type(a) is not type(b) for a, b in zip(before, after, strict=True)
                        ):
                            raise ValueError("la importacion no conserva los valores originales")
                if target.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("referencias historicas invalidas")
            with database.connect() as connection:
                if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("la base importada no supera la validacion")
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                connection.execute("PRAGMA journal_mode=DELETE")
            # Atomic publication without replacing a concurrent/pre-existing ledger.
            os.link(temporary, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Importar historial a una copia independiente")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        import_legacy(arguments.source, arguments.destination, arguments.archive)
    except (OSError, ValueError, sqlite3.Error):
        parser.exit(
            1,
            "No se pudo importar. El origen no se modifica ni se sobrescriben destinos. "
            "Revise las rutas y la compatibilidad del esquema; conserve la copia privada.\n",
        )
    print("Importacion verificada. Historial protegido; la copia es independiente del origen.")


if __name__ == "__main__":
    main()
