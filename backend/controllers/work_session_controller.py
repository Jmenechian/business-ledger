from backend.database import work_sessions
from backend.database.connection import Database
from backend.models.work_session import WorkSession
from backend.services.errors import LedgerError
from backend.services.movements import validate_key


def start(database: Database, key: str) -> tuple[WorkSession, bool]:
    validate_key(key)
    key = "group:" + key
    with database.transaction() as connection:
        existing = connection.execute(
            "SELECT id FROM work_sessions WHERE request_key=? AND kind='group'", (key,)
        ).fetchone()
        if existing:
            return work_sessions.summary(connection, existing["id"]), True
        if work_sessions.active(connection):
            raise LedgerError("ya hay una transferencia activa; actualice para retomarla", 409)
        row = connection.execute(
            "INSERT INTO work_sessions(kind,request_key) VALUES ('group',?) RETURNING id", (key,)
        ).fetchone()
        return work_sessions.summary(connection, row["id"]), False


def active(database: Database) -> WorkSession | None:
    with database.connect() as connection:
        connection.execute("BEGIN")
        row = work_sessions.active(connection)
        return work_sessions.summary(connection, row["id"]) if row else None


def history(database: Database) -> list[WorkSession]:
    with database.connect() as connection:
        connection.execute("BEGIN")
        ids = connection.execute(
            "SELECT id FROM work_sessions WHERE kind='group' ORDER BY id DESC LIMIT 50"
        ).fetchall()
        return [work_sessions.summary(connection, row["id"]) for row in ids]


def detail(database: Database, session_id: int) -> WorkSession:
    with database.connect() as connection:
        connection.execute("BEGIN")
        return work_sessions.summary(connection, session_id)


def finish(database: Database, session_id: int) -> WorkSession:
    with database.transaction() as connection:
        if work_sessions.get(connection, session_id)["kind"] != "group":
            raise LedgerError("esa sesión no es una transferencia de trabajo", 400)
        return work_sessions.finish(connection, session_id)
