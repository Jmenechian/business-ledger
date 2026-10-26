from typing import Literal

from pydantic import BaseModel

from backend.models.movement import Movement


class WorkEvent(BaseModel):
    id: int
    movement_id: int
    client_id: int
    client_name: str
    action: Literal["create", "edit", "delete"]
    recorded_at: str
    before: Movement | None
    after: Movement | None
    affected_before: list[Movement]
    affected_after: list[Movement]
    delta_debit: int
    delta_credit: int


class ClientActivity(BaseModel):
    client_id: int
    client_name: str
    debe: str
    haber: str
    neto: str


class WorkSession(BaseModel):
    id: int
    kind: Literal["group", "individual", "legacy"]
    started_at: str
    ended_at: str | None
    activity_count: int
    deliveries: int
    payments: int
    edits: int
    deletions: int
    debe: str
    haber: str
    neto: str
    clients: list[ClientActivity]
    events: list[WorkEvent]
