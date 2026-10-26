from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from backend.controllers import client_controller
from backend.controllers import movement_controller as controller
from backend.models.client import ClientCreate
from backend.models.movement import DeliveryCreate, PaymentCreate
from backend.services.errors import LedgerError
from backend.services.movements import delivery, payment


def test_edit_preserves_imports_order_metadata_and_retry(database):
    account = client_controller.create_client(database, ClientCreate(nombre="Sintético"))
    with database.transaction() as connection:
        connection.execute(
            """INSERT INTO movements
        (client_id,origin,kind,description,debit,credit,balance)
        VALUES (?,'imported','historical','Sintético',17.75,0,-7.5)""",
            (account.id,),
        )
    history = controller.get_movements(database, account.id)
    input = DeliveryCreate(detalle="Sintético", cant=1, precio_unitario=100)
    first, _ = controller.add_delivery(database, account.id, "a", input)
    second, _ = controller.add_payment(
        database, account.id, "b", PaymentCreate(fecha="2026-10-26", haber=Decimal(10))
    )
    replacement = delivery(
        DeliveryCreate(detalle="Cambio sintético", cant=2, precio_unitario=100, fecha="2000-01-01")
    )
    edited = controller.edit(database, account.id, first.id, first.revision, replacement)
    rows = controller.get_movements(database, account.id)
    assert rows[0] == history[0]
    assert edited.saldo == 193 and rows[-1].saldo == 183
    assert edited.added_date == first.added_date and edited.modified_at is not None
    assert rows[-1].revision > second.revision
    assert controller.add_delivery(database, account.id, "a", input) == (edited, True)
    for client_id, movement_id, revision, status in [
        (account.id, history[0].id, 1, 409),
        (account.id, first.id, 1, 409),
        (999999, first.id, 2, 404),
    ]:
        with pytest.raises(LedgerError) as error:
            controller.edit(database, client_id, movement_id, revision, replacement)
        assert error.value.status == status


def test_concurrent_edits_reject_stale_revisions(database):
    account = client_controller.create_client(database, ClientCreate(nombre="Sintético"))
    first, _ = controller.add_payment(
        database, account.id, "a", PaymentCreate(fecha="2026-10-26", haber=Decimal(100))
    )

    def edit(_):
        try:
            controller.edit(
                database,
                account.id,
                first.id,
                1,
                payment(PaymentCreate(fecha="2026-10-26", haber=Decimal(50))),
            )
            return 200
        except LedgerError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, range(2))) == [200, 409]


def test_edit_http_preconditions_and_kind(client):
    id = client.post("/api/clients", json={"nombre": "Sintético"}).json()["id"]
    first = client.post(
        f"/api/clients/{id}/payments",
        json={"fecha": "2026-10-26", "haber": 100},
        headers={"Idempotency-Key": "a"},
    ).json()
    path = f"/api/clients/{id}/movements/{first['id']}"
    for match in ["", "1", 'W/"1"', '"0"', '"01"', "*"]:
        assert (
            client.put(
                path + "/payment",
                json={"fecha": "2026-10-26", "haber": 50},
                headers={"If-Match": match},
            ).status_code
            == 428
        )
    assert (
        client.put(
            path + "/delivery",
            json={"detalle": "x", "cant": 1, "precio_unitario": 1},
            headers={"If-Match": '"1"'},
        ).status_code
        == 400
    )
    edited = client.put(
        path + "/payment", json={"fecha": "2026-10-26", "haber": 50}, headers={"If-Match": '"1"'}
    )
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    assert (
        client.put(
            path + "/payment",
            json={"fecha": "2026-10-26", "haber": 40},
            headers={"If-Match": '"1"'},
        ).status_code
        == 409
    )
