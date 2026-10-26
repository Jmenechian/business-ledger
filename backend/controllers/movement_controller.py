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
