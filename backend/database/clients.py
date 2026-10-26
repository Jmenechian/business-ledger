import sqlite3

from backend.models.client import Client
from backend.services.errors import not_found

CLIENT_COLUMNS = """
c.id, c.name AS nombre, c.created_at,
COALESCE((SELECT balance FROM movements m WHERE m.client_id=c.id AND m.deleted_at IS NULL
ORDER BY m.id DESC LIMIT 1), 0) AS saldo
"""


def create(connection: sqlite3.Connection, name: str) -> Client:
    row = connection.execute(
        "INSERT INTO clients(name) VALUES (?) RETURNING id, name AS nombre, 0 AS saldo, created_at",
        (name,),
    ).fetchone()
    return Client(**dict(row))


def list_all(connection: sqlite3.Connection) -> list[Client]:
    rows = connection.execute(
        f"SELECT {CLIENT_COLUMNS} FROM clients c ORDER BY c.name COLLATE NOCASE, c.id"
    ).fetchall()
    return [Client(**dict(row)) for row in rows]


def get(connection: sqlite3.Connection, client_id: int) -> Client:
    row = connection.execute(
        f"SELECT {CLIENT_COLUMNS} FROM clients c WHERE c.id=?", (client_id,)
    ).fetchone()
    if row is None:
        raise not_found()
    return Client(**dict(row))
