from fastapi import APIRouter

from backend.router.auth import router as auth
from backend.router.clients import router as clients
from backend.router.movements import router as movements
from backend.router.price_suggestions import router as price_suggestions
from backend.router.reports import router as reports
from backend.router.work_sessions import router as work_sessions

router = APIRouter(prefix="/api")
router.include_router(auth)
router.include_router(clients)
router.include_router(movements)
router.include_router(work_sessions)
router.include_router(price_suggestions)
router.include_router(reports)


@router.get("/health")
def health() -> dict[str, str]:
    return {"estado": "ok"}
