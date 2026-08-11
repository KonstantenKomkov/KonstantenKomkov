"""Tests for the stable runtime clock snapshot."""

from datetime import datetime, timezone

from it_activity.adapters.system_clock import SystemClock


def test_system_clock_captures_one_timezone_aware_instant() -> None:
    before = datetime.now(timezone.utc)
    clock = SystemClock()
    captured = clock.now()
    after = datetime.now(timezone.utc)

    assert before <= captured <= after
    assert captured.tzinfo is not None
    assert captured.utcoffset() is not None
    assert clock.now() == captured
