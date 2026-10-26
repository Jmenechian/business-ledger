"""Short-lived connections; each write transaction owns its connection."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

APPLICATION_ID = 1112294471


class Database:
    def __init__(self, path: Path):
        self.path = path.resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        migrations = sorted((Path(__file__).parent / "migrations").glob("*.sql"))
        with self.transaction() as connection:
            app = connection.execute("PRAGMA application_id").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if app == 0 and version == 0:
                tables = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchone()
                if tables:
                    raise ValueError("la base existente requiere importación explícita")
            elif app != APPLICATION_ID or not 1 <= version <= len(migrations):
                raise ValueError("base de datos o versión de esquema no compatible")
            for migration in migrations[version:]:
                # executescript commits implicitly; execute complete statements
                # instead so schema changes and version updates remain atomic.
                statement = ""
                for line in migration.read_text(encoding="utf-8").splitlines(True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ""
                if statement.strip():
                    raise ValueError("migración SQL incompleta")
        with self.connect() as connection:
            if connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                raise ValueError("no se pudo activar WAL")
