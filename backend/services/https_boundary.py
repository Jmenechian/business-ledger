"""ASGI boundary: configured transport, exact Host and same-origin mutations."""

from urllib.parse import urlsplit

from starlette.responses import JSONResponse

from backend.services.transport import origin_host


class HTTPSBoundary:
    def __init__(self, app, origin: str, allow_http: bool = False):
        self.app = app
        self.origin = origin
        self.host = origin_host(origin, allow_http=allow_http)
        self.scheme = urlsplit(origin).scheme

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] += [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (
                        b"content-security-policy",
                        b"default-src 'none'; script-src 'self'; style-src 'self'; "
                        b"connect-src 'self'; img-src 'self' data:; font-src 'self'; "
                        b"frame-ancestors 'none'; base-uri 'none'; "
                        b"form-action 'self'; object-src 'none'",
                    ),
                ]
            await send(message)

        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin-1")
        origin = headers.get(b"origin", b"").decode("latin-1")
        unsafe = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        status, error = 0, ""
        if scope["scheme"] != self.scheme:
            status, error = 426, "se requiere el protocolo configurado para este servidor"
        elif host != self.host:
            status, error = 403, "servidor no permitido"
        elif (
            (origin and origin != self.origin)
            or (unsafe and origin != self.origin)
            or headers.get(b"sec-fetch-site") == b"cross-site"
        ):
            status, error = 403, "origen no permitido"
        if status:
            await JSONResponse({"error": error}, status)(scope, receive, secure_send)
            return
        await self.app(scope, receive, secure_send)
