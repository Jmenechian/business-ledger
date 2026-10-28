"""Application factory: importing this module never opens a ledger file."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from backend.database.connection import Database
from backend.router.frontend import register_frontend
from backend.router.router import router
from backend.services.errors import LedgerError
from backend.services.https_boundary import HTTPSBoundary
from backend.services.passwords import Credential
from backend.services.session_boundary import SessionBoundary
from backend.services.sessions import AuthService, LoginLimit
from backend.services.transport import origin_host


def create_app(
    database_path: Path,
    *,
    origin: str,
    credential: Credential,
    frontend_directory: Path | None = None,
    allow_http: bool = False,
) -> FastAPI:
    origin_host(origin, allow_http=allow_http)
    database = Database(database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        yield

    app = FastAPI(
        title="Business Ledger",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    app.state.database = database
    app.state.auth = AuthService(credential)
    app.state.secure_cookies = origin.startswith("https:")
    app.state.cookie_name = "__Host-ledger" if app.state.secure_cookies else "ledger-http"
    app.add_middleware(SessionBoundary, auth=app.state.auth, cookie_name=app.state.cookie_name)
    app.add_middleware(HTTPSBoundary, origin=origin, allow_http=allow_http)

    @app.exception_handler(LedgerError)
    async def ledger_error(request: Request, error: LedgerError):
        headers = {"Retry-After": str(error.seconds)} if isinstance(error, LoginLimit) else None
        return JSONResponse({"error": str(error)}, status_code=error.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return JSONResponse(
            {"error": "los datos no son válidos o contienen campos no permitidos"},
            status_code=400,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        message = "método no permitido" if error.status_code == 405 else "ruta no encontrada"
        return JSONResponse(
            {"error": message}, status_code=error.status_code, headers=error.headers
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception):
        return JSONResponse({"error": "no se pudo completar la operación"}, status_code=500)

    app.include_router(router)
    register_frontend(
        app, frontend_directory or Path(__file__).resolve().parent.parent / "frontend" / "dist"
    )
    return app
