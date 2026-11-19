"""SQLite response cache keyed by (prompt, model, tool args).

Generic: nothing here knows about migrations, so any agent can reuse it.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

DEFAULT_PATH = Path(".migratelens/cache.sqlite")


def make_key(prompt: str, model: str, tool_args: dict | None = None) -> str:
    payload = json.dumps(
        {"prompt": prompt, "model": model, "tool_args": tool_args or {}},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Cache:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL, created REAL NOT NULL)"
        )
        self._db.commit()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> dict | None:
        row = self._db.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(row[0])

    def set(self, key: str, value: dict) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO cache (key, value, created) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()
