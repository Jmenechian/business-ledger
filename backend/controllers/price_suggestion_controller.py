from backend.database import clients, movements
from backend.database.connection import Database
from backend.models.price_suggestion import PriceSuggestion
from backend.services.price_suggestions import suggest


def get_suggestions(database: Database, client_id: int, query: str) -> list[PriceSuggestion]:
    with database.connect() as connection:
        clients.get(connection, client_id)
        history = movements.price_candidates(connection, client_id)
    return suggest(history, query)
