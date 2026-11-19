import json
import uuid

import sqlite3


def add_event(db: sqlite3.Connection, run_id: str, event_type: str, payload: dict) -> None:
    db.execute(
        """INSERT INTO agent_events (id, run_id, event_type, payload_json)
           VALUES (?, ?, ?, ?)""",
        (str(uuid.uuid4()), run_id, event_type, json.dumps(payload, ensure_ascii=False)),
    )


def run_response(row: sqlite3.Row) -> dict:
    proposal = json.loads(row["proposal_json"])
    files = []
    for item in proposal["files"]:
        body = item["content"]
        files.append(
            {
                "path": item["path"],
                "size_bytes": len(body.encode("utf-8")),
                "preview": body[:1200],
            }
        )
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "status": row["status"],
        "model": row["model"],
        "request": row["request"],
        "summary": proposal["summary"],
        "plan": proposal["plan"],
        "steps": proposal["steps"],
        "files": files,
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    }


def event_responses(db: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = db.execute(
        """SELECT id, event_type, payload_json, created_at
           FROM agent_events WHERE run_id = ? ORDER BY created_at, rowid""",
        (run_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
