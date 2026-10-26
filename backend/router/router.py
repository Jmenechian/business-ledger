from fastapi import APIRouter

from backend.router.auth import router as auth
from backend.router.clients import router as clients
from backend.router.movements import router as movements
from backend.router.work_sessions import router as work_sessions

router = APIRouter(prefix="/api")
router.include_router(auth)
router.include_router(clients)
router.include_router(movements)
router.include_router(work_sessions)


@router.get("/health")
def health() -> dict[str, str]:
    return {"estado": "ok"}
