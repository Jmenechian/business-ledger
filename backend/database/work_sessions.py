"""Private, append-only activity journal, committed with the ledger changes."""

import json
import sqlite3
from uuid import uuid4

from backend.models.movement import Movement
from backend.models.work_session import ClientActivity, WorkEvent, WorkSession
from backend.services.errors import LedgerError


def get(connection: sqlite3.Connection, session_id: int):
    row = connection.execute("SELECT * FROM work_sessions WHERE id=?", (session_id,)).fetchone()
    if row is None:
        raise LedgerError("transferencia no encontrada", 404)
    return row


def active(connection: sqlite3.Connection):
    return connection.execute(
        "SELECT * FROM work_sessions WHERE kind='group' AND ended_at IS NULL"
    ).fetchone()


def for_write(connection: sqlite3.Connection, session_id: int | None) -> tuple[int, bool]:
    current = active(connection)
    if session_id is not None:
        row = get(connection, session_id)
        if row["kind"] != "group" or row["ended_at"] is not None:
            raise LedgerError("la transferencia ya terminó; actualice la cuenta", 409)
        return row["id"], False
    if current:
        raise LedgerError("hay una transferencia activa; actualice la cuenta antes de guardar", 409)
    row = connection.execute(
        "INSERT INTO work_sessions(kind,request_key) VALUES ('individual',?) RETURNING id",
        ("individual:" + str(uuid4()),),
    ).fetchone()
    return row["id"], True


def record(
    connection: sqlite3.Connection,
    session_id: int,
    action: str,
    before: Movement | None,
    after: Movement | None,
    affected_before: list[Movement],
    affected_after: list[Movement],
) -> None:
    target = after or before
    name = connection.execute(
        "SELECT name FROM clients WHERE id=?", (target.client_id,)
    ).fetchone()[0]
    connection.execute(
        """INSERT INTO work_events
    (session_id,movement_id,client_id,client_name,action,before_json,after_json,
     affected_before_json,affected_after_json,delta_debit,delta_credit)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            session_id,
            target.id,
            target.client_id,
            name,
            action,
            before.model_dump_json() if before else None,
            after.model_dump_json() if after else None,
            json.dumps([row.model_dump() for row in affected_before], ensure_ascii=False),
            json.dumps([row.model_dump() for row in affected_after], ensure_ascii=False),
            int(after.debe if after else 0) - int(before.debe if before else 0),
            int(after.haber if after else 0) - int(before.haber if before else 0),
        ),
    )


def summary(connection: sqlite3.Connection, session_id: int) -> WorkSession:
    row = get(connection, session_id)
    if row["summary_json"]:
        return WorkSession.model_validate_json(row["summary_json"])
    events = []
    totals: dict[int, dict] = {}
    for entry in connection.execute(
        "SELECT * FROM work_events WHERE session_id=? ORDER BY id", (session_id,)
    ).fetchall():
        event = WorkEvent(
            id=entry["id"],
            movement_id=entry["movement_id"],
            client_id=entry["client_id"],
            client_name=entry["client_name"],
            action=entry["action"],
            recorded_at=entry["recorded_at"],
            before=json.loads(entry["before_json"]) if entry["before_json"] else None,
            after=json.loads(entry["after_json"]) if entry["after_json"] else None,
            affected_before=json.loads(entry["affected_before_json"]),
            affected_after=json.loads(entry["affected_after_json"]),
            delta_debit=entry["delta_debit"],
            delta_credit=entry["delta_credit"],
        )
        events.append(event)
        account = totals.setdefault(
            event.client_id, {"name": event.client_name, "debe": 0, "haber": 0}
        )
        account["debe"] += event.delta_debit
        account["haber"] += event.delta_credit
    debit = sum(event.delta_debit for event in events)
    credit = sum(event.delta_credit for event in events)
    return WorkSession(
        id=row["id"],
        kind=row["kind"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        activity_count=len(events),
        deliveries=sum(
            event.action == "create" and event.after.tipo == "delivery" for event in events
        ),
        payments=sum(
            event.action == "create" and event.after.tipo == "payment" for event in events
        ),
        edits=sum(event.action == "edit" for event in events),
        deletions=sum(event.action == "delete" for event in events),
        debe=str(debit),
        haber=str(credit),
        neto=str(debit - credit),
        clients=[
            ClientActivity(
                client_id=id,
                client_name=value["name"],
                debe=str(value["debe"]),
                haber=str(value["haber"]),
                neto=str(value["debe"] - value["haber"]),
            )
            for id, value in totals.items()
        ],
        events=events,
    )


def finish(connection: sqlite3.Connection, session_id: int) -> WorkSession:
    result = summary(connection, session_id)
    if result.ended_at:
        return result
    result.ended_at = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')").fetchone()[
        0
    ]
    connection.execute(
        "UPDATE work_sessions SET ended_at=?,summary_json=? WHERE id=?",
        (result.ended_at, result.model_dump_json(), session_id),
    )
    return result
