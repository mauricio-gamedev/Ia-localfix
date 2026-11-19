import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(database_path: Path) -> None:
    with connect(database_path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                workspace_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_memories_project
                ON memories(project_id);

            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                request TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('awaiting_approval', 'applying', 'completed', 'rejected', 'failed')
                ),
                proposal_json TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_agent_runs_project
                ON agent_runs(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS agent_events (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_agent_events_run
                ON agent_events(run_id, created_at);
            """
        )
        try:
            db.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                   USING fts5(memory_id UNINDEXED, content, tokenize='unicode61')"""
            )
        except sqlite3.OperationalError:
            # LIKE-based search remains available on SQLite builds without FTS5.
            pass


def fts_available(db: sqlite3.Connection) -> bool:
    try:
        db.execute("SELECT count(*) FROM memories_fts").fetchone()
        return True
    except sqlite3.OperationalError:
        return False
