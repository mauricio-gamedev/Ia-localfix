import sqlite3
from pathlib import Path


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


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
