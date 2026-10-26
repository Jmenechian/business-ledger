import sqlite3
from decimal import Decimal

import pytest

from backend.controllers import client_controller, movement_controller
from backend.models.client import ClientCreate
from backend.models.movement import DeliveryCreate, PaymentCreate
from backend.services.errors import LedgerError
from backend.services.money import MAX_AMOUNT


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
        path + "/payments", json={"haber": 150.49}, headers={"Idempotency-Key": "b"}
    )
    assert response.status_code == 201
    assert response.json()["saldo"] == -50
    assert response.json()["detalle"] == "Pago"
    retry = client.post(path + "/payments", json={"haber": 150.1}, headers={"Idempotency-Key": "b"})
    assert retry.status_code == 200 and retry.json() == response.json()
    assert client.get(f"/api/clients/{b}/movements").json() == []
    assert client.get(f"/api/clients/{b}").json()["saldo"] == 0
    assert (
        client.post(
            path + "/payments", json={"haber": 150}, headers={"Idempotency-Key": "a"}
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
        database, account.id, "a", PaymentCreate(haber=Decimal(10))
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
            database, account.id, "recoverable", PaymentCreate(haber=Decimal(1))
        )
    with database.transaction() as connection:
        connection.execute("DROP TRIGGER synthetic_failure")
    _, replay = movement_controller.add_payment(
        database, account.id, "recoverable", PaymentCreate(haber=Decimal(1))
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
