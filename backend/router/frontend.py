"""Serve only compiled application assets, independently from ledger access."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles


def register_frontend(app, directory: Path) -> None:
    router = APIRouter()

    @router.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def index():
        path = directory / "index.html"
        if not path.is_file():
            return JSONResponse({"error": "la interfaz todavía no está compilada"}, 503)
        return FileResponse(path, media_type="text/html")

    app.include_router(router)
    app.mount(
        "/assets", StaticFiles(directory=directory / "assets", check_dir=False), name="assets"
    )
