from typing import Annotated

from fastapi import APIRouter, Query

from backend.controllers import price_suggestion_controller
from backend.models.price_suggestion import PriceSuggestion
from backend.router.dependencies import ClientID, DatabaseDependency

router = APIRouter(prefix="/clients/{client_id}", tags=["Sugerencias de precios"])


@router.get("/price-suggestions", response_model=list[PriceSuggestion])
def get_suggestions(
    client_id: ClientID,
    database: DatabaseDependency,
    q: Annotated[str, Query(max_length=500)] = "",
):
    return price_suggestion_controller.get_suggestions(database, client_id, q)
