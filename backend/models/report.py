"""Immutable statement data, independent of HTTP and PDF layout."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StatementRow:
    number: int
    movement_id: int
    origin: str
    detalle: str
    cant: int | None
    precio_unitario: int | float | None
    price_is_derived: bool
    n_remito: str | None
    fecha: str | None
    debe: int | float
    haber: int | float
    saldo: int | float


@dataclass(frozen=True)
class Statement:
    client_id: int
    client_name: str
    generated_at: datetime
    timezone: str
    first_row_number: int
    last_row_number: int
    opening_balance: int | float
    final_balance: int | float
    rows: tuple[StatementRow, ...]
