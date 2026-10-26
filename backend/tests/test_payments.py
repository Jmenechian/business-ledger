import sqlite3
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.controllers import client_controller, movement_controller
from backend.models.client import ClientCreate
from backend.models.movement import DeliveryCreate, PaymentCreate
from backend.services.errors import LedgerError
from backend.services.money import MAX_AMOUNT


@pytest.mark.parametrize(
    "payload",
    [
        {"haber": 10},
        {"haber": 10, "fecha": ""},
        {"haber": 10, "fecha": " \t "},
        {"haber": 10, "fecha": None},
        {"haber": 10, "fecha": 20261026},
        {"haber": 10, "fecha": "2026-02-29"},
        {"haber": 10, "fecha": "2026-13-01"},
        {"haber": 10, "fecha": "26-Oct-2026"},
        {"haber": 10, "fecha": "2026-1-01"},
        {"haber": 10, "fecha": "2026-10-26T12:00:00Z"},
        {"fecha": "2026-10-26"},
    ],
)
def test_payment_requires_amount_and_valid_commercial_date_without_mutation(client, payload):
    with pytest.raises(ValidationError):
        PaymentCreate(**payload)
    account = client.post("/api/clients", json={"nombre": "Cuenta sintética"}).json()["id"]
    path = f"/api/clients/{account}"
    original = client.post(
        path + "/payments",
        json={"haber": 20, "fecha": "2024-02-29"},
        headers={"Idempotency-Key": "original"},
    ).json()
    before = client.get(path + "/movements").json()
    database = client.app.state.database

    def journal_counts():
        with database.connect() as connection:
            return (
                connection.execute("SELECT count(*) FROM work_events").fetchone()[0],
                connection.execute("SELECT count(*) FROM work_sessions").fetchone()[0],
            )

    counts = journal_counts()
    assert (
        client.post(
            path + "/payments", json=payload, headers={"Idempotency-Key": "recoverable"}
        ).status_code
        == 400
    )
    assert (
        client.put(
            path + f"/movements/{original['id']}/payment",
            json=payload,
            headers={"If-Match": f'"{original["revision"]}"'},
        ).status_code
        == 400
    )
    assert client.get(path + "/movements").json() == before
    assert client.get(path).json()["saldo"] == original["saldo"]
    assert journal_counts() == counts
    # Validation neither consumes an idempotency key nor increments a revision.
    assert (
        client.post(
            path + "/payments",
            json={"haber": 10, "fecha": "2026-10-26"},
            headers={"Idempotency-Key": "recoverable"},
        ).status_code
        == 201
    )
    corrected = client.put(
        path + f"/movements/{original['id']}/payment",
        json={"haber": 20, "fecha": "2026-10-25"},
        headers={"If-Match": f'"{original["revision"]}"'},
    )
    assert corrected.status_code == 200
    assert corrected.json()["fecha"] == "2026-10-25"
    assert corrected.json()["added_date"] == original["added_date"]


def test_payment_credit_settlement_and_client_isolation(client):
    a = client.post("/api/clients", json={"nombre": "Cuenta sintética A"}).json()["id"]
    b = client.post("/api/clients", json={"nombre": "Cuenta sintética B"}).json()["id"]
    path = f"/api/clients/{a}"
    client.post(
        path + "/deliveries",
        json={"detalle": "x", "cant": 1, "precio_unitario": 100},
        headers={"Idempotency-Key": "a"},
    )
    response = client.post(
        path + "/payments",
        json={"fecha": "2026-10-26", "haber": 150.49},
        headers={"Idempotency-Key": "b"},
    )
    assert response.status_code == 201
    assert response.json()["saldo"] == -50
    assert response.json()["detalle"] == "Pago"
    retry = client.post(
        path + "/payments",
        json={"fecha": "2026-10-26", "haber": 150.1},
        headers={"Idempotency-Key": "b"},
    )
    assert retry.status_code == 200 and retry.json() == response.json()
    assert client.get(f"/api/clients/{b}/movements").json() == []
    assert client.get(f"/api/clients/{b}").json()["saldo"] == 0
    assert (
        client.post(
            path + "/payments",
            json={"fecha": "2026-10-26", "haber": 150},
            headers={"Idempotency-Key": "a"},
        ).status_code
        == 409
    )
    settled = client.post(
        path + "/deliveries",
        json={"detalle": "x", "cant": 1, "precio_unitario": 50, "fecha": "2000-01-01"},
        headers={"Idempotency-Key": "c"},
    )
    assert settled.json()["saldo"] == 0
    assert client.get(path + "/movements").json()[-1]["id"] == settled.json()["id"]


def test_imported_discrepancies_and_triggers(database):
    account = client_controller.create_client(database, ClientCreate(nombre="Sintético"))
    with database.transaction() as connection:
        connection.execute(
            """INSERT INTO movements
            (client_id,origin,kind,description,quantity,unit_price,debit,credit,balance)
            VALUES (?,'imported','historical','Sintético',3,NULL,17.75,0,-7.5)""",
            (account.id,),
        )
    before = movement_controller.get_movements(database, account.id)
    row, _ = movement_controller.add_payment(
        database, account.id, "a", PaymentCreate(fecha="2026-10-26", haber=Decimal(10))
    )
    assert row.saldo == -18
    assert movement_controller.get_movements(database, account.id)[0] == before[0]
    assert before[0].precio_unitario is None and before[0].added_date is None
    for query in [
        "UPDATE movements SET balance=0 WHERE origin='imported'",
        "DELETE FROM movements WHERE origin='imported'",
        "INSERT INTO movements(client_id,origin,kind,description,debit,credit,balance) "
        "VALUES (1,'imported','historical','x',1,0,1)",
    ]:
        with pytest.raises(sqlite3.IntegrityError), database.transaction() as connection:
            connection.execute(query)


def test_overflow_and_failed_insert_do_not_consume_keys(database):
    account = client_controller.create_client(database, ClientCreate(nombre="Sintético"))
    with database.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER synthetic_failure BEFORE INSERT ON movements "
            "BEGIN SELECT RAISE(ABORT,'Synthetic failure'); END;"
        )
    with pytest.raises(sqlite3.IntegrityError):
        movement_controller.add_payment(
            database, account.id, "recoverable", PaymentCreate(fecha="2026-10-26", haber=Decimal(1))
        )
    with database.transaction() as connection:
        connection.execute("DROP TRIGGER synthetic_failure")
    _, replay = movement_controller.add_payment(
        database, account.id, "recoverable", PaymentCreate(fecha="2026-10-26", haber=Decimal(1))
    )
    assert not replay
    movement_controller.add_delivery(
        database,
        account.id,
        "limit",
        DeliveryCreate(detalle="Sintético", cant=1, precio_unitario=MAX_AMOUNT),
    )
    movement_controller.add_delivery(
        database, account.id, "one", DeliveryCreate(detalle="Sintético", cant=1, precio_unitario=1)
    )
    with pytest.raises(LedgerError):
        movement_controller.add_delivery(
            database,
            account.id,
            "overflow",
            DeliveryCreate(detalle="Sintético", cant=1, precio_unitario=1),
        )
    assert len(movement_controller.get_movements(database, account.id)) == 3
