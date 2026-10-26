from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.services.sessions import COOKIE_NAME, AuthService


class SessionBoundary:
    def __init__(self, app, auth: AuthService):
        self.app = app
        self.auth = auth

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        public = (scope["method"], scope["path"]) in {
            ("GET", "/api/health"),
            ("POST", "/api/auth/login"),
        }
        public = public or (
            scope["method"] in {"GET", "HEAD"}
            and (scope["path"] == "/" or scope["path"].startswith("/assets/"))
        )
        token = Request(scope).cookies.get(COOKIE_NAME, "")
        if not public and not self.auth.authenticate(token):
            await JSONResponse({"error": "inicie sesión para continuar"}, 401)(scope, receive, send)
            return
        await self.app(scope, receive, send)
