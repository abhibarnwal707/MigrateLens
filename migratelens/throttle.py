"""Rate limiting for free-tier APIs: RPM throttle, backoff on 429/503, daily budget.

Generic: usable with any rate-limited API.
"""

from __future__ import annotations

import json
import random
import time
from collections import deque
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


class DailyBudgetExceeded(RuntimeError):
    pass


class RetryableError(Exception):
    """Raise (or wrap) errors that deserve a retry, e.g. HTTP 429 or 503."""


class RpmThrottle:
    """Blocks so that no more than `rpm` calls start in any rolling 60 s window."""

    def __init__(self, rpm: int, clock=time.monotonic, sleep=time.sleep):
        self.rpm = rpm
        self._clock = clock
        self._sleep = sleep
        self._stamps: deque[float] = deque()

    def wait(self) -> None:
        now = self._clock()
        while self._stamps and now - self._stamps[0] >= 60:
            self._stamps.popleft()
        if len(self._stamps) >= self.rpm:
            delay = 60 - (now - self._stamps[0])
            if delay > 0:
                self._sleep(delay)
            now = self._clock()
            while self._stamps and now - self._stamps[0] >= 60:
                self._stamps.popleft()
        self._stamps.append(self._clock())


class DailyBudget:
    """Persistent per-day request counter that refuses to go past `limit`."""

    def __init__(self, limit: int, path: str | Path = ".migratelens/budget.json", today=date.today):
        self.limit = limit
        self.path = Path(path)
        self._today = today
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        if data.get("day") != self._today().isoformat():
            data = {"day": self._today().isoformat(), "count": 0}
        return data

    @property
    def used(self) -> int:
        return self._load()["count"]

    def consume(self) -> None:
        data = self._load()
        if data["count"] >= self.limit:
            raise DailyBudgetExceeded(
                f"daily budget of {self.limit} requests reached; stopping before the API limit"
            )
        data["count"] += 1
        self.path.write_text(json.dumps(data))


def with_backoff[T](
    fn: Callable[[], T],
    *,
    retries: int = 5,
    base: float = 2.0,
    cap: float = 60.0,
    sleep=time.sleep,
    is_retryable: Callable[[Exception], bool] = lambda e: isinstance(e, RetryableError),
) -> T:
    """Call fn(); on a retryable error wait base*2**n (+jitter, capped) and retry."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - classification is delegated to is_retryable
            if attempt >= retries or not is_retryable(exc):
                raise
            sleep(min(cap, base * 2**attempt) + random.uniform(0, 0.5))
            attempt += 1
