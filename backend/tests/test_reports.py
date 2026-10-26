from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.controllers import client_controller, movement_controller, report_controller
from backend.models.client import ClientCreate
from backend.models.movement import DeliveryCreate, PaymentCreate
from backend.router import reports
from backend.services.errors import LedgerError


def synthetic_account(database):
    return client_controller.create_client(database, ClientCreate(nombre="Cuenta sintética"))


def imported_row(database, client_id, *, debit, balance, quantity=2, price=None, date=None):
    with database.transaction() as connection:
        return connection.execute(
            """INSERT INTO movements
            (client_id,origin,kind,description,quantity,unit_price,business_date,debit,credit,balance)
            VALUES (?,'imported','historical','Producto sintético',?,?,?, ?,0,?) RETURNING id""",
            (client_id, quantity, price, date, debit, balance),
        ).fetchone()[0]


def test_statement_preserves_imported_values_and_customer_row_numbers(database):
    other = synthetic_account(database)
    imported_row(database, other.id, debit=999, balance=123)
    account = synthetic_account(database)
    first = imported_row(database, account.id, debit=17.75, balance=-7.5)
    second = imported_row(database, account.id, debit=31, balance=8.25, date="2001-02-03")
    last, _ = movement_controller.add_delivery(
        database,
        account.id,
        "synthetic-new",
        DeliveryCreate(detalle="Nueva sintética", cant=1, precio_unitario=10),
    )
    before = movement_controller.get_movements(database, account.id)
    report = report_controller.get_statement(database, account.id, second)
    assert report.client_id == account.id
    assert report.first_row_number == 2 and report.last_row_number == 3
    assert report.opening_balance == -7.5 and type(report.opening_balance) is float
    assert report.final_balance == 18 and type(report.final_balance) is int
    assert [row.number for row in report.rows] == [2, 3]
    assert [row.movement_id for row in report.rows] == [second, last.id]
    assert report.rows[0].debe == 31 and report.rows[0].saldo == 8.25
    assert report.rows[0].precio_unitario == 16 and report.rows[0].price_is_derived
    assert report.rows[0].fecha == "2001-02-03"
    assert report.rows[1].precio_unitario == 10 and not report.rows[1].price_is_derived
    assert movement_controller.get_movements(database, account.id) == before
    assert before[1].precio_unitario is None
    first_report = report_controller.get_statement(database, account.id, first)
    assert first_report.opening_balance == 0
    assert first_report.rows[0].fecha is None
    last_report = report_controller.get_statement(database, account.id, last.id)
    assert len(last_report.rows) == 1 and last_report.opening_balance == 8.25
    assert last_report.first_row_number == last_report.last_row_number == 3
    with pytest.raises(FrozenInstanceError):
        report.opening_balance = 0
    with pytest.raises(FrozenInstanceError):
        report.rows[0].saldo = 0


def test_statement_derivation_retains_original_price_and_large_historical_values(database):
    account = synthetic_account(database)
    first = imported_row(database, account.id, debit=5, balance=9, price=0)
    imported_row(database, account.id, debit=5, balance=10, quantity=0)
    imported_row(database, account.id, debit=0, balance=11)
    imported_row(database, account.id, debit=9223372036854775807, balance=12, quantity=1)
    report = report_controller.get_statement(database, account.id, first)
    assert [(row.precio_unitario, row.price_is_derived) for row in report.rows] == [
        (0, False),
        (None, False),
        (None, False),
        (9223372036854775807, True),
    ]


def test_statement_excludes_deleted_rows_and_rejects_other_customer(database):
    account, other = synthetic_account(database), synthetic_account(database)
    deleted, _ = movement_controller.add_payment(
        database, account.id, "deleted", PaymentCreate(haber=Decimal(5))
    )
    kept, _ = movement_controller.add_payment(
        database, account.id, "kept", PaymentCreate(haber=Decimal(8))
    )
    movement_controller.delete(database, account.id, deleted.id, deleted.revision)
    report = report_controller.get_statement(database, account.id, kept.id)
    assert report.first_row_number == report.last_row_number == 1
    assert report.opening_balance == 0 and report.final_balance == -8
    for client_id, start in [
        (account.id, deleted.id),
        (other.id, kept.id),
        (99999, kept.id),
        (account.id, 99999),
    ]:
        with pytest.raises(LedgerError) as error:
            report_controller.get_statement(database, client_id, start)
        assert error.value.status == 404


def test_statement_uses_consistent_read_snapshot_without_write_lock(database, monkeypatch):
    account = synthetic_account(database)
    row, _ = movement_controller.add_payment(
        database, account.id, "first", PaymentCreate(haber=Decimal(10))
    )
    original_history = report_controller.movements.get_history
    trace = []
    original_connect = database.connect

    @contextmanager
    def traced_connect():
        with original_connect() as connection:
            connection.set_trace_callback(trace.append)
            yield connection

    monkeypatch.setattr(database, "connect", traced_connect)

    def read_then_concurrent_write(connection, client_id):
        # WAL writer can commit while the report holds its older read snapshot.
        movement_controller.add_payment(
            database, account.id, "concurrent", PaymentCreate(haber=Decimal(20))
        )
        return original_history(connection, client_id)

    monkeypatch.setattr(report_controller.movements, "get_history", read_then_concurrent_write)
    report = report_controller.get_statement(database, account.id, row.id)
    assert report.final_balance == -10 and len(report.rows) == 1
    assert trace[0] == "BEGIN"
    assert trace[-1] == "ROLLBACK"
    assert any(statement == "BEGIN IMMEDIATE" for statement in trace)


def test_statement_download_is_authenticated_and_has_no_mutations(
    client, anonymous_client, monkeypatch
):
    account = client.post("/api/clients", json={"nombre": 'Sintética " / <nombre>'}).json()
    path = f"/api/clients/{account['id']}"
    row = client.post(
        path + "/payments", json={"haber": 20}, headers={"Idempotency-Key": "synthetic"}
    ).json()
    history = client.get(path + "/movements").json()
    sessions = client.get("/api/work-sessions").json()
    captured = []

    def fake_render(statement):
        captured.append(statement)
        return b"%PDF-1.4\n% synthetic transport fixture"

    monkeypatch.setattr(reports, "render_pdf", fake_render)
    url = path + f"/reports/statement.pdf?from_movement_id={row['id']}"
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="cuenta-{account["id"]}-movimientos-1-1.pdf"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"%PDF-") and len(captured) == 1
    assert client.get(path + "/movements").json() == history
    assert client.get("/api/work-sessions").json() == sessions
    for query in ["", "?from_movement_id=0", "?from_movement_id=-1", "?from_movement_id=x"]:
        assert client.get(path + "/reports/statement.pdf" + query).status_code == 400
    assert client.get(path + "/reports/statement.pdf?from_movement_id=99999").status_code == 404
    client.post("/api/auth/logout")
    assert anonymous_client.get(url).status_code == 401
    assert len(captured) == 1
