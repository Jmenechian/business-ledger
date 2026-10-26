"""Capture one consistent, read-only customer statement before rendering."""

from datetime import UTC, datetime
from fractions import Fraction

from backend.database import clients, movements
from backend.database.connection import Database
from backend.models.movement import Movement
from backend.models.report import Statement, StatementRow
from backend.services.errors import not_found


def statement_price(movement: Movement) -> tuple[int | float | None, bool]:
    if movement.precio_unitario is not None:
        return movement.precio_unitario, False
    if movement.cant is None or movement.cant <= 0 or movement.debe <= 0:
        return None, False
    # Historical amounts need not fit the limits for new movements. Use exact
    # decimal arithmetic without imposing new-entry limits on their display.
    value = Fraction(str(movement.debe)) / movement.cant
    integer, remainder = divmod(value.numerator, value.denominator)
    return integer + (2 * remainder >= value.denominator), True


def get_statement(
    database: Database,
    client_id: int,
    from_movement_id: int,
    *,
    timezone: str = "America/Buenos_Aires",
) -> Statement:
    with database.connect() as connection:
        connection.execute("BEGIN")
        try:
            client = clients.get(connection, client_id)
            history = movements.get_history(connection, client_id)
            start = next(
                (index for index, row in enumerate(history) if row.id == from_movement_id),
                None,
            )
            if start is None:
                raise not_found()
            opening_balance = history[start - 1].saldo if start else 0
            rows = []
            for number, movement in enumerate(history[start:], start + 1):
                price, derived = statement_price(movement)
                rows.append(
                    StatementRow(
                        number=number,
                        movement_id=movement.id,
                        origin=movement.origin,
                        detalle=movement.detalle,
                        cant=movement.cant,
                        precio_unitario=price,
                        price_is_derived=derived,
                        n_remito=movement.n_remito,
                        fecha=movement.fecha,
                        debe=movement.debe,
                        haber=movement.haber,
                        saldo=movement.saldo,
                    )
                )
            report = Statement(
                client_id=client.id,
                client_name=client.nombre,
                generated_at=datetime.now(UTC),
                timezone=timezone,
                first_row_number=start + 1,
                last_row_number=len(history),
                opening_balance=opening_balance,
                final_balance=history[-1].saldo,
                rows=tuple(rows),
            )
        finally:
            # Ending a read transaction never writes ledger or journal state.
            connection.rollback()
    return report
