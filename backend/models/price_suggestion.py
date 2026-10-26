from pydantic import BaseModel


class PriceReference(BaseModel):
    movement_id: int
    detalle: str
    precio_original: int | float | None
    precio_unitario: int
    precio_derivado: bool
    fecha: str | None
    added_date: str | None


class PriceSuggestion(BaseModel):
    detalle: str
    similitud: float
    referencias: list[PriceReference]
