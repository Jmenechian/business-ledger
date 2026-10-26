from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from backend.controllers import client_controller, movement_controller
from backend.models.client import ClientCreate
from backend.models.movement import DeliveryCreate
from backend.services.errors import LedgerError


def delivery(**changes):
    return DeliveryCreate(
        detalle="Producto sintético", cant=2, precio_unitario=Decimal("1000.5"), **changes
    )


def test_delivery_history_and_retry(client):
    id = client.post("/api/clients", json={"nombre": "Cuenta sintética"}).json()["id"]
    path = f"/api/clients/{id}"
    payload = {"detalle": "Producto sintético", "cant": 2, "precio_unitario": 1000.5}
    first = client.post(path + "/deliveries", json=payload, headers={"Idempotency-Key": "a"})
    assert first.status_code == 201
    assert first.json()["saldo"] == 2002
    assert first.json()["fecha"] is None
    retry = client.post(path + "/deliveries", json=payload, headers={"Idempotency-Key": "a"})
    assert retry.status_code == 200 and retry.json() == first.json()
    assert retry.headers["Idempotency-Replayed"] == "true"
    assert client.get(path + "/movements").json() == [first.json()]
    assert client.get(path).json()["saldo"] == 2002
    payload["cant"] = 3
    assert (
        client.post(
            path + "/deliveries", json=payload, headers={"Idempotency-Key": "a"}
        ).status_code
        == 409
    )
    assert client.post(path + "/deliveries", json=payload).status_code == 400


@pytest.mark.parametrize(
    "price,quantity,expected",
    [
        ("1000.49", 3, 3000),
        ("1000.5", 3, 3003),
        ("0.5", 1, 1),
        ("9007199254740990.49", 1, 9007199254740990),
    ],
)
def test_exact_rounding(client, price, quantity, expected):
    id = client.post("/api/clients", json={"nombre": "Sintético"}).json()["id"]
    response = client.post(
        f"/api/clients/{id}/deliveries",
        content='{"detalle":"Sintético","cant":'
        + str(quantity)
        + ',"precio_unitario":'
        + price
        + "}",
        headers={"Content-Type": "application/json", "Idempotency-Key": "x"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["debe"] == expected


@pytest.mark.parametrize(
    "payload",
    [
        '{"detalle":"x","cant":1,"precio_unitario":1e999999}',
        '{"detalle":"x","cant":1,"precio_unitario":1e-999999}',
        '{"detalle":"x","cant":true,"precio_unitario":10}',
        '{"detalle":"x","cant":1.5,"precio_unitario":10}',
        '{"detalle":"x","cant":1,"precio_unitario":"10"}',
        '{"detalle":"x","cant":1,"debe":10}',
        '{"detalle":"x","cant":1,"precio_unitario":NaN}',
        '{"detalle":"x","cant":1,"precio_unitario":10,"fecha":"2025-02-29"}',
        '{"detalle":" ","cant":1,"precio_unitario":10}',
        "null",
        "{}",
    ],
)
def test_invalid_deliveries(client, payload):
    id = client.post("/api/clients", json={"nombre": "Sintético"}).json()["id"]
    response = client.post(
        f"/api/clients/{id}/deliveries",
        content=payload,
        headers={"Content-Type": "application/json", "Idempotency-Key": "x"},
    )
    assert response.status_code == 400, response.text
    assert client.get(f"/api/clients/{id}/movements").json() == []


def test_concurrent_retries_and_persistent_keys(database):
    account = client_controller.create_client(database, ClientCreate(nombre="Sintético"))

    def add(index):
        return movement_controller.add_delivery(
            database, account.id, f"key-{index // 2}", delivery()
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add, range(20)))
    rows = movement_controller.get_movements(database, account.id)
    assert len(rows) == 10
    assert [row.saldo for row in rows] == [2002 * i for i in range(1, 11)]
    database.initialize()
    assert add(0)[1]
    with pytest.raises(LedgerError):
        movement_controller.add_delivery(database, 999999, "missing", delivery())
