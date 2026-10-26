from typing import Annotated

from fastapi import APIRouter, Header, Response

from backend.controllers import movement_controller
from backend.models.movement import DeliveryCreate, Movement, PaymentCreate
from backend.router.dependencies import ClientID, DatabaseDependency
from backend.router.json_route import ExactJSONRoute

router = APIRouter(prefix="/clients/{client_id}", tags=["Movimientos"], route_class=ExactJSONRoute)
RetryKey = Annotated[str, Header(alias="Idempotency-Key")]


@router.get("/movements", response_model=list[Movement])
def get_movements(client_id: ClientID, database: DatabaseDependency):
    return movement_controller.get_movements(database, client_id)


def movement_response(response: Response, result: tuple[Movement, bool]) -> Movement:
    movement, replay = result
    response.status_code = 200 if replay else 201
    if replay:
        response.headers["Idempotency-Replayed"] = "true"
    return movement


@router.post("/deliveries", status_code=201, response_model=Movement)
def add_delivery(
    client_id: ClientID,
    input: DeliveryCreate,
    database: DatabaseDependency,
    response: Response,
    idempotency_key: RetryKey = "",
):
    return movement_response(
        response, movement_controller.add_delivery(database, client_id, idempotency_key, input)
    )


@router.post("/payments", status_code=201, response_model=Movement)
def add_payment(
    client_id: ClientID,
    input: PaymentCreate,
    database: DatabaseDependency,
    response: Response,
    idempotency_key: RetryKey = "",
):
    return movement_response(
        response, movement_controller.add_payment(database, client_id, idempotency_key, input)
    )
