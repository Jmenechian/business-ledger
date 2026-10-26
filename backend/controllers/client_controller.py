from backend.database import clients
from backend.database.connection import Database
from backend.models.client import Client, ClientCreate


def create_client(database: Database, input: ClientCreate) -> Client:
    with database.transaction() as connection:
        return clients.create(connection, input.nombre)


def get_clients(database: Database) -> list[Client]:
    with database.connect() as connection:
        return clients.list_all(connection)


def get_client(database: Database, client_id: int) -> Client:
    with database.connect() as connection:
        return clients.get(connection, client_id)
