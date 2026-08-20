from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from software_factory.domain import FactorySession, SessionEvent, WorkflowState


class SQLiteSessionRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS events_session_id_id
                ON events(session_id, id);
                """
            )

    def create(self, session: FactorySession) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO sessions(id, goal, state, created_at, updated_at, result_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._values(session),
            )

    def get(self, session_id: str) -> FactorySession | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def list_sessions(self, limit: int = 50) -> list[FactorySession]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def save(self, session: FactorySession) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE sessions
                SET goal = ?, state = ?, created_at = ?, updated_at = ?, result_json = ?, error = ?
                WHERE id = ?
                """,
                (
                    session.goal,
                    session.state.value,
                    session.created_at,
                    session.updated_at,
                    json.dumps(session.result) if session.result is not None else None,
                    session.error,
                    session.id,
                ),
            )

    def append_event(self, event: SessionEvent) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO events(session_id, kind, actor, message, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.session_id,
                    event.kind,
                    event.actor,
                    event.message,
                    json.dumps(event.payload),
                    event.created_at,
                ),
            )

    def events(self, session_id: str, after: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM events WHERE session_id = ? AND id > ? ORDER BY id",
                (session_id, after),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "kind": row["kind"],
                "actor": row["actor"],
                "message": row["message"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    @staticmethod
    def _values(session: FactorySession) -> tuple[object, ...]:
        return (
            session.id,
            session.goal,
            session.state.value,
            session.created_at,
            session.updated_at,
            json.dumps(session.result) if session.result is not None else None,
            session.error,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> FactorySession:
        return FactorySession(
            id=row["id"],
            goal=row["goal"],
            state=WorkflowState(row["state"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
        )
