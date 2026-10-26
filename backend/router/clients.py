from fastapi import APIRouter, Response

from backend.controllers import client_controller
from backend.models.client import Client, ClientCreate
from backend.router.dependencies import ClientID, DatabaseDependency
from backend.router.json_route import ExactJSONRoute

router = APIRouter(prefix="/clients", tags=["Clientes"], route_class=ExactJSONRoute)


@router.post("", status_code=201, response_model=Client)
def create_client(input: ClientCreate, database: DatabaseDependency, response: Response):
    client = client_controller.create_client(database, input)
    response.headers["Location"] = f"/api/clients/{client.id}"
    return client


@router.get("", response_model=list[Client])
def get_clients(database: DatabaseDependency):
    return client_controller.get_clients(database)


@router.get("/{client_id}", response_model=Client)
def get_client(client_id: ClientID, database: DatabaseDependency):
    return client_controller.get_client(database, client_id)
