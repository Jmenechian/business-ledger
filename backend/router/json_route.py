"""Bounded JSON decoding that preserves decimal literals before validation."""

import json
from decimal import Decimal

from fastapi import Request
from fastapi.routing import APIRoute

from backend.services.errors import LedgerError


def number(text: str):
    if len(text) > 64:
        raise LedgerError("el número supera el límite permitido")
    return Decimal(text) if any(c in text.lower() for c in ".e") else int(text)


def invalid_constant(text: str):
    raise LedgerError("se requieren números finitos")


class ExactJSONRequest(Request):
    async def json(self):
        if not hasattr(self, "_json"):
            body = await self.body()
            try:
                self._json = json.loads(
                    body,
                    parse_float=number,
                    parse_int=number,
                    parse_constant=invalid_constant,
                )
            except (ValueError, UnicodeDecodeError):
                raise LedgerError("el cuerpo JSON no es válido") from None
        return self._json


class ExactJSONRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            if self.body_field is not None and request.method in {"POST", "PUT", "PATCH"}:
                media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if media != "application/json":
                    raise LedgerError("se requiere Content-Type application/json")
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 16 * 1024:
                        raise LedgerError("el cuerpo JSON supera el límite permitido")
                request = ExactJSONRequest(request.scope, request.receive)
                request._body = bytes(body)
            return await handler(request)

        return handle
