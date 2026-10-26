from fastapi import APIRouter

from backend.router.clients import router as clients
from backend.router.movements import router as movements

router = APIRouter(prefix="/api")
router.include_router(clients)
router.include_router(movements)


@router.get("/health")
def health() -> dict[str, str]:
    return {"estado": "ok"}
