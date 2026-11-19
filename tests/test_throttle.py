from datetime import date, timedelta

import pytest

from migratelens.throttle import (
    DailyBudget,
    DailyBudgetExceeded,
    RetryableError,
    RpmThrottle,
    with_backoff,
)


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def test_rpm_throttle_waits_when_full():
    clk = FakeClock()
    th = RpmThrottle(2, clock=clk.now, sleep=clk.sleep)
    th.wait()
    th.wait()
    assert clk.sleeps == []
    th.wait()  # third call within 60 s must wait
    assert clk.sleeps and clk.sleeps[0] == pytest.approx(60)


def test_backoff_retries_then_succeeds():
    calls = {"n": 0}
    sleeps = []

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RetryableError("429")
        return "ok"

    assert with_backoff(fn, sleep=sleeps.append) == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]


def test_backoff_gives_up_and_skips_non_retryable():
    with pytest.raises(RetryableError):
        with_backoff(
            lambda: (_ for _ in ()).throw(RetryableError("x")), retries=2, sleep=lambda s: None
        )
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise ValueError("nope")

    with pytest.raises(ValueError):
        with_backoff(bad, sleep=lambda s: None)
    assert calls["n"] == 1


def test_daily_budget_stops_and_resets(tmp_path):
    day = {"d": date(2026, 1, 1)}
    b = DailyBudget(2, tmp_path / "b.json", today=lambda: day["d"])
    b.consume()
    b.consume()
    with pytest.raises(DailyBudgetExceeded):
        b.consume()
    day["d"] += timedelta(days=1)
    b.consume()
    assert b.used == 1
