import sqlite3
from decimal import Decimal

import pytest

from backend.controllers import client_controller
from backend.controllers import movement_controller as controller
from backend.database.connection import Database
from backend.models.client import ClientCreate
from backend.models.movement import DeliveryCreate, PaymentCreate
from backend.services.errors import LedgerError
from backend.services.money import MAX_AMOUNT
from backend.services.movements import payment


def test_delete_keys_survive_restart_and_last_native_boundary(database):
    account = client_controller.create_client(database, ClientCreate(nombre="Sintético"))
    other = client_controller.create_client(database, ClientCreate(nombre="Otra cuenta sintética"))
    original = PaymentCreate(fecha="2026-10-26", haber=Decimal(10))
    first, _ = controller.add_payment(database, account.id, "a", original)
    with pytest.raises(LedgerError) as error:
        controller.delete(database, other.id, first.id, first.revision)
    assert error.value.status == 404
    controller.delete(database, account.id, first.id, first.revision)
    assert controller.get_movements(database, account.id) == []
    assert client_controller.get_client(database, account.id).saldo == 0
    reopened = Database(database.path)
    reopened.initialize()
    for input, status in [
        (original, 410),
        (PaymentCreate(fecha="2026-10-26", haber=Decimal(20)), 409),
    ]:
        with pytest.raises(LedgerError) as error:
            controller.add_payment(reopened, account.id, "a", input)
        assert error.value.status == status
    with pytest.raises(sqlite3.IntegrityError), reopened.transaction() as connection:
        connection.execute("DELETE FROM movements WHERE id=?", (first.id,))
    with pytest.raises(sqlite3.IntegrityError), reopened.transaction() as connection:
        connection.execute(
            """INSERT INTO movements
        (client_id,origin,kind,description,debit,credit,balance)
        VALUES (?,'imported','historical','Sintético',1,0,1)""",
            (account.id,),
        )
    second, _ = controller.add_payment(reopened, account.id, "new-intent", original)
    assert second.saldo == -10 and second.id > first.id


def test_overflow_rolls_back_edit_and_deletion(database):
    account = client_controller.create_client(database, ClientCreate(nombre="Sintético"))
    first, _ = controller.add_payment(
        database, account.id, "a", PaymentCreate(fecha="2026-10-26", haber=Decimal(100))
    )
    controller.add_delivery(
        database, account.id, "b", DeliveryCreate(detalle="x", cant=1, precio_unitario=MAX_AMOUNT)
    )
    controller.add_delivery(
        database, account.id, "c", DeliveryCreate(detalle="x", cant=1, precio_unitario=100)
    )
    before = controller.get_movements(database, account.id)
    with pytest.raises(LedgerError):
        controller.edit(
            database,
            account.id,
            first.id,
            1,
            payment(PaymentCreate(fecha="2026-10-26", haber=Decimal(1))),
        )
    assert controller.get_movements(database, account.id) == before
    with pytest.raises(LedgerError):
        controller.delete(database, account.id, first.id, 1)
    assert controller.get_movements(database, account.id) == before


def test_delete_recalculates_from_imported_fraction_and_http_retry(client):
    account = client.post("/api/clients", json={"nombre": "Sintético"}).json()
    database = client.app.state.database
    with database.transaction() as connection:
        connection.execute(
            """INSERT INTO movements
        (client_id,origin,kind,description,debit,credit,balance)
        VALUES (?,'imported','historical','Sintético',17.75,0,-7.5)""",
            (account["id"],),
        )
    path = f"/api/clients/{account['id']}"
    a = client.post(
        path + "/deliveries",
        json={"detalle": "x", "cant": 1, "precio_unitario": 100},
        headers={"Idempotency-Key": "a"},
    ).json()
    client.post(
        path + "/payments",
        json={"fecha": "2026-10-26", "haber": 10},
        headers={"Idempotency-Key": "b"},
    )
    assert (
        client.delete(path + f"/movements/{a['id']}", headers={"If-Match": '"1"'}).status_code
        == 204
    )
    rows = client.get(path + "/movements").json()
    assert len(rows) == 2 and rows[0]["saldo"] == -7.5 and rows[-1]["saldo"] == -18
    assert client.get(path).json()["saldo"] == -18
    assert (
        client.post(
            path + "/deliveries",
            json={"detalle": "x", "cant": 1, "precio_unitario": 100},
            headers={"Idempotency-Key": "a"},
        ).status_code
        == 410
    )
