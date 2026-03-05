"""Tests for Lumon time.* built-in namespace."""

from __future__ import annotations

import time as _time

import pytest


@pytest.fixture
def run(runner):
    def _run(code):
        return runner.run(code)
    return _run


# ===================================================================
# time.now
# ===================================================================

class TestTimeNow:
    def test_returns_positive_number(self, run):
        r = run('return time.now()')
        assert r.value > 0

    def test_close_to_python_time(self, run):
        before = _time.time() * 1000
        r = run('return time.now()')
        after = _time.time() * 1000
        assert before <= r.value <= after

    def test_is_milliseconds(self, run):
        r = run('return time.now()')
        # Should be in the billions (ms since epoch)
        assert r.value > 1_000_000_000_000


# ===================================================================
# time.wait
# ===================================================================

class TestTimeWait:
    def test_returns_none(self, run):
        r = run('return time.wait(0)')
        assert r.value is None

    def test_actually_waits(self, run):
        before = _time.time()
        run('return time.wait(50)')
        elapsed = (_time.time() - before) * 1000
        assert elapsed >= 40  # allow some slack

    def test_zero_instant(self, run):
        before = _time.time()
        r = run('return time.wait(0)')
        elapsed = (_time.time() - before) * 1000
        assert r.value is None
        assert elapsed < 500

    def test_negative_errors(self, run):
        r = run('return time.wait(-1)')
        assert r.error is not None
        assert "negative" in r.error["message"]

    def test_over_cap_errors(self, run):
        r = run('return time.wait(60001)')
        assert r.error is not None
        assert "60000" in r.error["message"]


# ===================================================================
# time.format
# ===================================================================

class TestTimeFormat:
    def test_format_date(self, run):
        # 2024-01-15 00:00:00 UTC = 1705276800000 ms
        r = run('return time.format(1705276800000, "%Y-%m-%d")')
        assert r.value == "2024-01-15"

    def test_format_datetime(self, run):
        r = run('return time.format(1705276800000, "%Y-%m-%d %H:%M:%S")')
        assert r.value == "2024-01-15 00:00:00"

    def test_format_time_only(self, run):
        # 1705276800000 + 3661000 ms = 01:01:01
        r = run('return time.format(1705280461000, "%H:%M:%S")')
        assert r.value == "01:01:01"

    def test_format_epoch_zero(self, run):
        r = run('return time.format(0, "%Y-%m-%d")')
        assert r.value == "1970-01-01"

    def test_format_invalid_timestamp_errors(self, run):
        r = run('return time.format(99999999999999999, "%Y-%m-%d")')
        assert r.error is not None
        assert "time.format" in r.error["message"]


# ===================================================================
# time.parse
# ===================================================================

class TestTimeParse:
    def test_parse_date(self, run):
        r = run('return time.parse("2024-01-15", "%Y-%m-%d")')
        assert r.value == pytest.approx(1705276800000, abs=1)

    def test_parse_datetime(self, run):
        r = run('return time.parse("2024-01-15 01:01:01", "%Y-%m-%d %H:%M:%S")')
        assert r.value == pytest.approx(1705280461000, abs=1)

    def test_invalid_returns_none(self, run):
        r = run('return time.parse("not-a-date", "%Y-%m-%d")')
        assert r.value is None

    def test_mismatch_returns_none(self, run):
        r = run('return time.parse("2024-01-15", "%H:%M:%S")')
        assert r.value is None

    def test_roundtrip_with_format(self, run):
        r = run(
            'let ts = time.parse("2024-06-01", "%Y-%m-%d") ?? 0\n'
            'return time.format(ts, "%Y-%m-%d")'
        )
        assert r.value == "2024-06-01"


# ===================================================================
# time.since
# ===================================================================

class TestTimeSince:
    def test_past_returns_positive(self, run):
        r = run('return time.since(0)')
        assert r.value > 0

    def test_now_returns_near_zero(self, run):
        r = run(
            'let t = time.now()\n'
            'return time.since(t)'
        )
        assert abs(r.value) < 1000  # within 1 second

    def test_future_returns_negative(self, run):
        r = run('return time.since(9999999999999)')
        assert r.value < 0


# ===================================================================
# time.date
# ===================================================================

class TestTimeDate:
    def test_returns_map(self, run):
        r = run('return time.date()')
        assert isinstance(r.value, dict)

    def test_has_all_fields(self, run):
        r = run('return time.date()')
        for key in ("year", "month", "day", "hour", "minute", "second"):
            assert key in r.value, f"missing field: {key}"

    def test_fields_are_numbers(self, run):
        r = run('return time.date()')
        for key in ("year", "month", "day", "hour", "minute", "second"):
            assert isinstance(r.value[key], (int, float))

    def test_year_reasonable(self, run):
        r = run('return time.date()')
        assert 2020 <= r.value["year"] <= 2100

    def test_field_access_works(self, run):
        r = run(
            'let d = time.date()\n'
            'return d.year'
        )
        assert 2020 <= r.value <= 2100


# ===================================================================
# time.add
# ===================================================================

class TestTimeAdd:
    def test_add_positive(self, run):
        r = run('return time.add(1000, 500)')
        assert r.value == 1500

    def test_add_negative(self, run):
        r = run('return time.add(1000, -500)')
        assert r.value == 500

    def test_add_zero(self, run):
        r = run('return time.add(1000, 0)')
        assert r.value == 1000

    def test_add_with_now(self, run):
        r = run(
            'let t = time.now()\n'
            'return time.add(t, 60000) > t'
        )
        assert r.value is True


# ===================================================================
# time.diff
# ===================================================================

class TestTimeDiff:
    def test_positive_diff(self, run):
        r = run('return time.diff(2000, 1000)')
        assert r.value == 1000

    def test_negative_diff(self, run):
        r = run('return time.diff(1000, 2000)')
        assert r.value == -1000

    def test_zero_diff(self, run):
        r = run('return time.diff(1000, 1000)')
        assert r.value == 0


# ===================================================================
# time.timeout
# ===================================================================

class TestTimeTimeout:
    def test_fast_fn_returns_ok(self, run):
        r = run('return time.timeout(5000, fn() -> 42)')
        assert r.value is not None
        assert r.value["tag"] == "ok"
        assert r.value["value"] == 42

    def test_slow_fn_returns_timeout(self, run):
        r = run('return time.timeout(50, fn() -> time.wait(5000))')
        assert r.value is not None
        assert r.value["tag"] == "timeout"

    def test_negative_ms_errors(self, run):
        r = run('return time.timeout(-1, fn() -> 42)')
        assert r.error is not None
        assert "negative" in r.error["message"]

    def test_over_cap_errors(self, run):
        r = run('return time.timeout(60001, fn() -> 42)')
        assert r.error is not None
        assert "60000" in r.error["message"]

    def test_fn_error_propagates(self, run):
        r = run('return time.timeout(5000, fn() -> time.wait(-1))')
        assert r.error is not None
        assert "negative" in r.error["message"]
