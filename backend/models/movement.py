import re
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, field_validator


def monetary_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError("se requiere un importe numérico")
    return value


Amount = Annotated[Decimal, BeforeValidator(monetary_number)]


class MovementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_remito: str = ""
    fecha: str = ""

    @field_validator("n_remito", "fecha", mode="before")
    @classmethod
    def optional_text(cls, value):
        if not isinstance(value, str):
            raise ValueError("se requiere texto")
        return value.strip()

    @field_validator("n_remito")
    @classmethod
    def reference_length(cls, value):
        if len(value) > 100:
            raise ValueError("el remito supera el límite permitido")
        return value

    @field_validator("fecha")
    @classmethod
    def business_date(cls, value):
        if value and (
            not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
            or date.fromisoformat(value).isoformat() != value
        ):
            raise ValueError("la fecha debe ser válida y tener formato YYYY-MM-DD")
        return value


class DeliveryCreate(MovementInput):
    detalle: str = Field(strict=True, min_length=1, max_length=500)
    cant: StrictInt = Field(gt=0, le=9007199254740991)
    precio_unitario: Amount

    @field_validator("detalle", mode="before")
    @classmethod
    def description(cls, value):
        return value.strip() if isinstance(value, str) else value


class PaymentCreate(MovementInput):
    haber: Amount
    detalle: str = Field(default="Pago", strict=True, max_length=500)

    @field_validator("detalle", mode="before")
    @classmethod
    def description(cls, value):
        return value.strip() or "Pago" if isinstance(value, str) else value


class Movement(BaseModel):
    id: int = 0
    client_id: int = 0
    origin: str = "native"
    tipo: str
    detalle: str
    cant: int | None = None
    precio_unitario: int | float | None = None
    n_remito: str | None = None
    fecha: str | None = None
    added_date: str | None = None
    debe: int | float = 0
    haber: int | float = 0
    saldo: int | float = 0
