import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from backend.controllers import client_controller
from backend.controllers import movement_controller as movements
from backend.controllers import work_session_controller as sessions
from backend.database.connection import Database
from backend.models.client import ClientCreate
from backend.models.movement import DeliveryCreate, PaymentCreate
from backend.services.errors import LedgerError
from backend.services.money import MAX_AMOUNT
from backend.services.movements import delivery


def account(database, name="Cuenta sintética"):
    return client_controller.create_client(database, ClientCreate(nombre=name))


def test_group_summary_audit_restart_and_frozen_close(database):
    a, b = account(database), account(database, "Otra cuenta sintética")
    group, replay = sessions.start(database, "start-a")
    assert not replay and sessions.start(database, "start-a") == (group, True)
    first, _ = movements.add_delivery(
        database,
        a.id,
        "a",
        DeliveryCreate(detalle="Entrega sintética", cant=2, precio_unitario=100),
        group.id,
    )
    paid, _ = movements.add_payment(
        database, b.id, "b", PaymentCreate(fecha="2026-10-26", haber=Decimal(50)), group.id
    )
    edited = movements.edit(
        database,
        a.id,
        first.id,
        first.revision,
        delivery(DeliveryCreate(detalle="Cambio sintético", cant=3, precio_unitario=100)),
        group.id,
    )
    movements.delete(database, b.id, paid.id, paid.revision, group.id)
    reopened = Database(database.path)
    reopened.initialize()
    current = sessions.active(reopened)
    assert current.id == group.id and current.activity_count == 4
    assert (current.deliveries, current.payments, current.edits, current.deletions) == (1, 1, 1, 1)
    assert (current.debe, current.haber, current.neto) == ("300", "0", "300")
    assert current.events[2].before == first and current.events[2].after == edited
    assert current.events[3].before == paid and current.events[3].after is None
    assert current.events[3].affected_before == [paid]
    closed = sessions.finish(reopened, group.id)
    assert closed.ended_at and sessions.active(reopened) is None
    assert sessions.finish(reopened, group.id) == closed
    # A later correction is recorded separately; original membership and closed summary stay fixed.
    corrected = movements.edit(
        reopened,
        a.id,
        edited.id,
        edited.revision,
        delivery(DeliveryCreate(detalle="Corrección posterior", cant=1, precio_unitario=100)),
    )
    assert corrected.work_session_id == group.id
    assert sessions.detail(reopened, group.id) == closed
    assert sessions.history(reopened) == [closed]
    replayed, replay = movements.add_delivery(
        reopened,
        a.id,
        "a",
        DeliveryCreate(detalle="Entrega sintética", cant=2, precio_unitario=100),
        group.id,
    )
    assert replay and replayed == corrected
    assert sessions.detail(reopened, group.id).activity_count == 4
    with pytest.raises(LedgerError) as error:
        movements.add_payment(
            reopened, b.id, "b", PaymentCreate(fecha="2026-10-26", haber=Decimal(50)), group.id
        )
    assert error.value.status == 410
    with reopened.connect() as connection:
        assert connection.execute("SELECT count(*) FROM work_events").fetchone()[0] == 5


def test_stale_or_missing_group_cannot_misattribute_writes(database):
    a = account(database)
    group, _ = sessions.start(database, "a")
    input = PaymentCreate(fecha="2026-10-26", haber=Decimal(10))
    with pytest.raises(LedgerError):
        movements.add_payment(database, a.id, "missing", input)
    assert movements.get_movements(database, a.id) == []
    sessions.finish(database, group.id)
    with pytest.raises(LedgerError):
        movements.add_payment(database, a.id, "stale", input, group.id)
    assert movements.get_movements(database, a.id) == []


def test_concurrent_start_has_one_active_group(database):
    def start(key):
        try:
            return sessions.start(database, key)[0].id
        except LedgerError as error:
            assert error.status == 409
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(start, ["first", "second"]))
    assert sum(value is not None for value in result) == 1
    assert sessions.active(database).id in result


def test_journal_failure_rolls_back_movement_and_individual_session(database):
    a = account(database)
    with database.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER synthetic_audit_failure BEFORE INSERT ON work_events "
            "BEGIN SELECT RAISE(ABORT,'Synthetic journal failure'); END;"
        )
    with pytest.raises(sqlite3.IntegrityError):
        movements.add_payment(
            database, a.id, "recoverable", PaymentCreate(fecha="2026-10-26", haber=Decimal(10))
        )
    assert movements.get_movements(database, a.id) == []
    with database.transaction() as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM work_sessions WHERE kind='individual'"
            ).fetchone()[0]
            == 0
        )
        connection.execute("DROP TRIGGER synthetic_audit_failure")
    assert not movements.add_payment(
        database, a.id, "recoverable", PaymentCreate(fecha="2026-10-26", haber=Decimal(10))
    )[1]


def test_closed_summaries_and_journal_cannot_be_changed(database):
    a = account(database)
    group, _ = sessions.start(database, "a")
    movements.add_payment(
        database, a.id, "a", PaymentCreate(fecha="2026-10-26", haber=Decimal(10)), group.id
    )
    sessions.finish(database, group.id)
    for sql in [
        "UPDATE work_events SET delta_credit=0",
        "DELETE FROM work_events",
        "UPDATE work_sessions SET summary_json='{}'",
        "DELETE FROM work_sessions",
    ]:
        with pytest.raises(sqlite3.IntegrityError), database.transaction() as connection:
            connection.execute(sql)


def test_summary_totals_are_exact_beyond_javascript_integer_range(database):
    a = account(database)
    group, _ = sessions.start(database, "a")
    for key, kind in [("a", "delivery"), ("b", "payment"), ("c", "delivery")]:
        if kind == "delivery":
            movements.add_delivery(
                database,
                a.id,
                key,
                DeliveryCreate(detalle="Límite sintético", cant=1, precio_unitario=MAX_AMOUNT),
                group.id,
            )
        else:
            movements.add_payment(
                database,
                a.id,
                key,
                PaymentCreate(fecha="2026-10-26", haber=Decimal(MAX_AMOUNT)),
                group.id,
            )
    result = sessions.finish(database, group.id)
    assert result.debe == str(MAX_AMOUNT * 2) and result.haber == str(MAX_AMOUNT)


def test_authenticated_group_api_and_idempotent_close(client, anonymous_client):
    client.cookies.clear()
    assert client.get("/api/work-sessions").status_code == 401
    password = "Contraseña sintética de pruebas 42"
    assert client.post("/api/auth/login", json={"password": password}).status_code == 200
    response = client.post("/api/work-sessions", headers={"Idempotency-Key": "group-a"})
    assert response.status_code == 201
    group = response.json()
    assert client.get("/api/work-sessions/active").json()["id"] == group["id"]
    assert (
        client.post("/api/work-sessions", headers={"Idempotency-Key": "group-a"}).status_code == 200
    )
    a = client.post("/api/clients", json={"nombre": "Cuenta sintética"}).json()["id"]
    assert (
        client.post(
            f"/api/clients/{a}/payments",
            json={"fecha": "2026-10-26", "haber": 10},
            headers={"Idempotency-Key": "a"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/clients/{a}/payments",
            json={"fecha": "2026-10-26", "haber": 10},
            headers={"Idempotency-Key": "a", "X-Work-Session": str(group["id"])},
        ).status_code
        == 201
    )
    closed = client.post(f"/api/work-sessions/{group['id']}/finish")
    assert closed.status_code == 200 and closed.json()["activity_count"] == 1
    assert client.post(f"/api/work-sessions/{group['id']}/finish").json() == closed.json()
