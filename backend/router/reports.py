"""Authenticated, read-only PDF statements; exporting has no ledger effects."""

from typing import Annotated

from fastapi import APIRouter, Query, Response

from backend.controllers.report_controller import get_statement
from backend.models.report import Statement
from backend.router.dependencies import ClientID, DatabaseDependency

router = APIRouter(prefix="/clients/{client_id}/reports", tags=["Reportes"])


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
    # Numeric identifiers avoid inserting untrusted customer text in headers.
    filename = (
        f"cuenta-{statement.client_id}-"
        f"movimientos-{statement.first_row_number}-{statement.last_row_number}.pdf"
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
