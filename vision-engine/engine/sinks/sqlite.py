"""Sink que grava todo evento em SQLite local — histórico consultável."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from engine.sinks.base import Sink
from engine.types import Event

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    identity TEXT,
    score REAL,
    bbox TEXT,
    data TEXT,
    timestamp REAL NOT NULL
);
"""


class SQLiteSink(Sink):
    def __init__(self, path: str = "events.db"):
        db_path = Path(path)
        if db_path.parent != Path("."):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def handle(self, event: Event) -> None:
        self._conn.execute(
            "INSERT INTO events (type, track_id, identity, score, bbox, data, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.type,
                event.track_id,
                event.identity,
                event.score,
                json.dumps(event.bbox) if event.bbox else None,
                json.dumps(event.data),
                event.timestamp,
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
