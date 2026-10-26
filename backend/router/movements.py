from typing import Annotated

from fastapi import APIRouter, Header, Response

from backend.controllers import movement_controller
from backend.models.movement import DeliveryCreate, Movement, PaymentCreate
from backend.router.dependencies import ClientID, DatabaseDependency, MovementID, Revision
from backend.router.json_route import ExactJSONRoute
from backend.services import movements as rules

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


@router.put("/movements/{movement_id}/delivery", response_model=Movement)
def edit_delivery(
    client_id: ClientID,
    movement_id: MovementID,
    input: DeliveryCreate,
    revision: Revision,
    database: DatabaseDependency,
):
    return movement_controller.edit(
        database, client_id, movement_id, revision, rules.delivery(input)
    )


@router.put("/movements/{movement_id}/payment", response_model=Movement)
def edit_payment(
    client_id: ClientID,
    movement_id: MovementID,
    input: PaymentCreate,
    revision: Revision,
    database: DatabaseDependency,
):
    return movement_controller.edit(
        database, client_id, movement_id, revision, rules.payment(input)
    )


@router.delete("/movements/{movement_id}", status_code=204)
def delete_movement(
    client_id: ClientID, movement_id: MovementID, revision: Revision, database: DatabaseDependency
):
    movement_controller.delete(database, client_id, movement_id, revision)
    return Response(status_code=204)
