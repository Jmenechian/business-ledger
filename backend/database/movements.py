import sqlite3

from backend.models.movement import Movement

MOVEMENT_COLUMNS = """
id, client_id, origin, kind AS tipo, description AS detalle, quantity AS cant,
unit_price AS precio_unitario, reference AS n_remito, business_date AS fecha,
created_at AS added_date, debit AS debe, credit AS haber, balance AS saldo
"""


def get_history(connection: sqlite3.Connection, client_id: int) -> list[Movement]:
    rows = connection.execute(
        f"SELECT {MOVEMENT_COLUMNS} FROM movements WHERE client_id=? ORDER BY id", (client_id,)
    ).fetchall()
    return [Movement(**dict(row)) for row in rows]


def last_balance(connection: sqlite3.Connection, client_id: int) -> int | float:
    row = connection.execute(
        "SELECT balance FROM movements WHERE client_id=? ORDER BY id DESC LIMIT 1", (client_id,)
    ).fetchone()
    return row[0] if row else 0


def find_request(connection: sqlite3.Connection, client_id: int, key: str):
    return connection.execute(
        f"SELECT {MOVEMENT_COLUMNS}, request_hash FROM movements "
        "WHERE client_id=? AND request_key=?",
        (client_id, key),
    ).fetchone()


def insert(
    connection: sqlite3.Connection,
    client_id: int,
    key: str,
    digest: str,
    movement: Movement,
    balance: int,
) -> Movement:
    row = connection.execute(
        f"""INSERT INTO movements
        (client_id, origin, kind, description, quantity, unit_price, reference,
         business_date, created_at, debit, credit, balance, request_key, request_hash)
        VALUES (?, 'native', ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?, ?, ?, ?, ?)
        RETURNING {MOVEMENT_COLUMNS}""",
        (
            client_id,
            movement.tipo,
            movement.detalle,
            movement.cant,
            movement.precio_unitario,
            movement.n_remito,
            movement.fecha,
            movement.debe,
            movement.haber,
            balance,
            key,
            digest,
        ),
    ).fetchone()
    return Movement(**dict(row))
