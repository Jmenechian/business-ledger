import sqlite3

from backend.models.movement import Movement
from backend.services.errors import not_found

MOVEMENT_COLUMNS = """
id, client_id, origin, kind AS tipo, description AS detalle, quantity AS cant,
unit_price AS precio_unitario, reference AS n_remito, business_date AS fecha,
created_at AS added_date, debit AS debe, credit AS haber, balance AS saldo, revision, modified_at,
work_session_id
"""


def get_history(connection: sqlite3.Connection, client_id: int) -> list[Movement]:
    rows = connection.execute(
        f"SELECT {MOVEMENT_COLUMNS} FROM movements "
        "WHERE client_id=? AND deleted_at IS NULL ORDER BY id",
        (client_id,),
    ).fetchall()
    return [Movement(**dict(row)) for row in rows]


def last_balance(connection: sqlite3.Connection, client_id: int) -> int | float:
    row = connection.execute(
        "SELECT balance FROM movements WHERE client_id=? AND deleted_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (client_id,),
    ).fetchone()
    return row[0] if row else 0


def find_request(connection: sqlite3.Connection, client_id: int, key: str):
    return connection.execute(
        f"SELECT {MOVEMENT_COLUMNS}, request_hash, deleted_at FROM movements "
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
    session_id: int,
) -> Movement:
    row = connection.execute(
        f"""INSERT INTO movements
        (client_id, origin, kind, description, quantity, unit_price, reference,
         business_date, created_at, debit, credit, balance, request_key, request_hash,
         work_session_id)
        VALUES (?, 'native', ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                ?, ?, ?, ?, ?, ?)
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
            session_id,
        ),
    ).fetchone()
    return Movement(**dict(row))


def get(connection: sqlite3.Connection, client_id: int, movement_id: int) -> Movement:
    row = connection.execute(
        f"SELECT {MOVEMENT_COLUMNS} FROM movements "
        "WHERE client_id=? AND id=? AND deleted_at IS NULL",
        (client_id, movement_id),
    ).fetchone()
    if row is None:
        raise not_found()
    return Movement(**dict(row))


def replace(connection: sqlite3.Connection, movement_id: int, movement: Movement) -> None:
    connection.execute(
        """UPDATE movements SET description=?, quantity=?, unit_price=?, reference=?,
        business_date=?, debit=?, credit=?, modified_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
        WHERE id=?""",
        (
            movement.detalle,
            movement.cant,
            movement.precio_unitario,
            movement.n_remito,
            movement.fecha,
            movement.debe,
            movement.haber,
            movement_id,
        ),
    )


def balance_before(connection: sqlite3.Connection, client_id: int, movement_id: int) -> int | float:
    row = connection.execute(
        "SELECT balance FROM movements WHERE client_id=? AND id<? AND deleted_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (client_id, movement_id),
    ).fetchone()
    return row[0] if row else 0


def affected(connection: sqlite3.Connection, client_id: int, movement_id: int) -> list[Movement]:
    rows = connection.execute(
        f"SELECT {MOVEMENT_COLUMNS} FROM movements "
        "WHERE client_id=? AND id>=? AND deleted_at IS NULL ORDER BY id",
        (client_id, movement_id),
    ).fetchall()
    return [Movement(**dict(row)) for row in rows]


def update_balance(connection: sqlite3.Connection, movement_id: int, balance: int) -> None:
    connection.execute(
        "UPDATE movements SET balance=?, revision=revision+1 WHERE id=?", (balance, movement_id)
    )


def mark_deleted(connection: sqlite3.Connection, movement_id: int) -> None:
    connection.execute(
        """UPDATE movements SET deleted_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        modified_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), revision=revision+1 WHERE id=?""",
        (movement_id,),
    )
