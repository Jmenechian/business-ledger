"""Authenticated, read-only PDF statements; exporting has no ledger effects."""

import re
import unicodedata
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query, Response

from backend.controllers.report_controller import get_statement
from backend.models.report import Statement
from backend.router.dependencies import ClientID, DatabaseDependency

router = APIRouter(prefix="/clients/{client_id}/reports", tags=["Reportes"])
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f]')


def summary_filename(client_name: str) -> str:
    name = INVALID_FILENAME.sub("_", client_name) or "Cliente"
    return f"Resumen {name}.pdf"


def download_disposition(client_name: str) -> str:
    filename = summary_filename(client_name)
    ascii_name = unicodedata.normalize("NFKD", client_name).encode("ascii", "ignore").decode()
    fallback = summary_filename(ascii_name if ascii_name.strip() else "Cliente")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


def render_pdf(statement: Statement) -> bytes:
    from backend.services.statement_pdf import render_statement

    return render_statement(statement)


@router.get("/statement.pdf")
def download_statement(
    client_id: ClientID,
    database: DatabaseDependency,
    from_movement_id: Annotated[int, Query(gt=0)],
) -> Response:
    statement = get_statement(database, client_id, from_movement_id)
    content = render_pdf(statement)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": download_disposition(statement.client_name)},
    )
