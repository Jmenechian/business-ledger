"""Loopback-only boundary until the HTTPS authentication milestone."""

import ipaddress
from urllib.parse import urlsplit

from starlette.responses import JSONResponse


class LocalBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin-1")
        try:
            hostname = urlsplit("http://" + host).hostname
            allowed = hostname == "localhost" or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            allowed = False
        origin = headers.get(b"origin", b"").decode("latin-1")
        if not allowed or (origin and origin != "http://" + host):
            await JSONResponse({"error": "servidor u origen no permitido"}, 403)(
                scope, receive, send
            )
            return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] += [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)

        await self.app(scope, receive, secure_send)
