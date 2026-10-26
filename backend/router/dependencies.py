from typing import Annotated

from fastapi import Depends, Header, Path, Request

from backend.database.connection import Database
from backend.services.errors import LedgerError


def get_database(request: Request) -> Database:
    return request.app.state.database


DatabaseDependency = Annotated[Database, Depends(get_database)]
ClientID = Annotated[int, Path(gt=0)]
MovementID = Annotated[int, Path(gt=0)]


def get_revision(if_match: Annotated[str, Header()] = "") -> int:
    text = if_match.removeprefix('"').removesuffix('"')
    if not text.isascii() or not text.isdigit() or len(text) > 16:
        raise LedgerError("se requiere If-Match con la revisión entre comillas", 428)
    revision = int(text)
    if revision <= 0 or if_match != f'"{revision}"':
        raise LedgerError("se requiere If-Match con la revisión entre comillas", 428)
    return revision


Revision = Annotated[int, Depends(get_revision)]
WorkSessionHeader = Annotated[int | None, Header(alias="X-Work-Session", gt=0)]
