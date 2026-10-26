import hashlib
import json

from backend.models.movement import DeliveryCreate, Movement
from backend.services.errors import LedgerError
from backend.services.money import MAX_AMOUNT, positive_amount


def delivery(input: DeliveryCreate) -> Movement:
    price = positive_amount(input.precio_unitario)
    if input.cant > MAX_AMOUNT // price:
        raise LedgerError("el importe de la entrega supera el límite permitido")
    return Movement(
        tipo="delivery",
        detalle=input.detalle,
        cant=input.cant,
        precio_unitario=price,
        debe=input.cant * price,
        n_remito=input.n_remito or None,
        fecha=input.fecha or None,
    )


def fingerprint(client_id: int, movement: Movement) -> str:
    # Keep the original Go creation JSON shape, field order and escaping so
    # existing request keys remain effective when upgrading the backend.
    fields = (
        "id",
        "client_id",
        "origin",
        "tipo",
        "detalle",
        "cant",
        "precio_unitario",
        "n_remito",
        "fecha",
        "added_date",
        "debe",
        "haber",
        "saldo",
    )
    payload = {name: getattr(movement, name) for name in fields}
    payload["client_id"] = client_id
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    for character, escaped in [
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ]:
        encoded = encoded.replace(character, escaped)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_key(key: str) -> None:
    if not 1 <= len(key) <= 128 or any(not 33 <= ord(character) <= 126 for character in key):
        raise LedgerError("se requiere Idempotency-Key de hasta 128 caracteres ASCII sin espacios")
