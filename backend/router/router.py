from fastapi import APIRouter

from backend.router.clients import router as clients

router = APIRouter(prefix="/api")
router.include_router(clients)


@router.get("/health")
def health() -> dict[str, str]:
    return {"estado": "ok"}
