"""Tests for public activity report invariants."""

from datetime import date, datetime, timedelta, timezone

import pytest

from it_activity.domain.activity import (
    ActivityDataError,
    ActivityReport,
    CommitMetadata,
    DailyActivity,
)


def test_commit_metadata_normalizes_sha_email_and_timezone() -> None:
    metadata = CommitMetadata(
        sha="A" * 40,
        authored_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone(timedelta(hours=3))),
        author_email=" OWNER@EXAMPLE.INVALID ",
    )

    assert metadata.sha == "a" * 40
    assert metadata.authored_at == datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    assert metadata.author_email == "owner@example.invalid"
    assert "owner@example.invalid" not in repr(metadata)


def test_activity_report_returns_trailing_totals() -> None:
    report = ActivityReport(
        timezone="Europe/Moscow",
        days=(
            DailyActivity(date(2026, 8, 8), commits=1, added_lines=10, deleted_lines=2),
            DailyActivity(date(2026, 8, 9), commits=2, added_lines=5, deleted_lines=3),
            DailyActivity(date(2026, 8, 10), commits=3, added_lines=7, deleted_lines=1),
        ),
    )

    totals = report.totals(2)

    assert totals.commits == 5
    assert totals.added_lines == 12
    assert totals.deleted_lines == 4


def test_activity_report_rejects_non_consecutive_days() -> None:
    with pytest.raises(ActivityDataError, match="подряд"):
        ActivityReport(
            timezone="UTC",
            days=(DailyActivity(date(2026, 8, 8)), DailyActivity(date(2026, 8, 10))),
        )
