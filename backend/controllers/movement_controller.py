from backend.database import clients, movements
from backend.database.connection import Database
from backend.models.movement import DeliveryCreate, Movement, PaymentCreate
from backend.services import movements as rules
from backend.services.errors import LedgerError
from backend.services.money import next_balance


def get_movements(database: Database, client_id: int) -> list[Movement]:
    with database.connect() as connection:
        clients.get(connection, client_id)
        return movements.get_history(connection, client_id)


def append(
    database: Database, client_id: int, key: str, movement: Movement
) -> tuple[Movement, bool]:
    rules.validate_key(key)
    digest = rules.fingerprint(client_id, movement)
    with database.transaction() as connection:
        clients.get(connection, client_id)
        previous = movements.find_request(connection, client_id, key)
        if previous:
            if previous["request_hash"] != digest:
                raise LedgerError("la clave de reintento ya se utilizó con otros datos", 409)
            if previous["deleted_at"] is not None:
                raise LedgerError(
                    "el movimiento fue eliminado; la clave no puede reutilizarse", 410
                )
            fields = {name: previous[name] for name in Movement.model_fields}
            return Movement(**fields), True
        balance = next_balance(
            movements.last_balance(connection, client_id), movement.debe, movement.haber
        )
        return movements.insert(connection, client_id, key, digest, movement, balance), False


def add_delivery(database: Database, client_id: int, key: str, input: DeliveryCreate):
    return append(database, client_id, key, rules.delivery(input))


def add_payment(database: Database, client_id: int, key: str, input: PaymentCreate):
    return append(database, client_id, key, rules.payment(input))


def edit(
    database: Database, client_id: int, movement_id: int, revision: int, replacement: Movement
) -> Movement:
    with database.transaction() as connection:
        old = movements.get(connection, client_id, movement_id)
        validate_correction(old, revision)
        if old.tipo != replacement.tipo:
            raise LedgerError("no se puede cambiar el tipo de movimiento")
        movements.replace(connection, movement_id, replacement)
        recalculate(connection, client_id, movement_id)
        return movements.get(connection, client_id, movement_id)


def validate_correction(old: Movement, revision: int) -> None:
    if old.origin != "native":
        raise LedgerError("el historial importado no se puede modificar", 409)
    if old.revision != revision:
        raise LedgerError("el movimiento cambió; actualice el historial antes de corregirlo", 409)


def delete(database: Database, client_id: int, movement_id: int, revision: int) -> None:
    with database.transaction() as connection:
        old = movements.get(connection, client_id, movement_id)
        validate_correction(old, revision)
        movements.mark_deleted(connection, movement_id)
        recalculate(connection, client_id, movement_id)


def recalculate(connection, client_id: int, movement_id: int) -> None:
    previous = movements.balance_before(connection, client_id, movement_id)
    for movement in movements.affected(connection, client_id, movement_id):
        if movement.origin != "native":
            raise LedgerError("el historial importado no se puede modificar", 409)
        balance = next_balance(previous, movement.debe, movement.haber)
        movements.update_balance(connection, movement.id, balance)
        previous = balance
