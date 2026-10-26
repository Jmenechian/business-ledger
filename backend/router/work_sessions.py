from fastapi import APIRouter, Response

from backend.controllers import work_session_controller as controller
from backend.models.work_session import WorkSession
from backend.router.dependencies import DatabaseDependency
from backend.router.movements import RetryKey

router = APIRouter(prefix="/work-sessions", tags=["Transferencias de trabajo"])


@router.post("", response_model=WorkSession, status_code=201)
def start(database: DatabaseDependency, response: Response, idempotency_key: RetryKey = ""):
    result, replay = controller.start(database, idempotency_key)
    if replay:
        response.status_code = 200
        response.headers["Idempotency-Replayed"] = "true"
    return result


@router.get("/active", response_model=WorkSession | None)
def active(database: DatabaseDependency):
    return controller.active(database)


@router.get("", response_model=list[WorkSession])
def history(database: DatabaseDependency):
    return controller.history(database)


@router.get("/{session_id}", response_model=WorkSession)
def detail(session_id: int, database: DatabaseDependency):
    return controller.detail(database, session_id)


@router.post("/{session_id}/finish", response_model=WorkSession)
def finish(session_id: int, database: DatabaseDependency):
    return controller.finish(database, session_id)
