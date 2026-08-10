"""Tests for all-or-nothing profile generation orchestration."""

from collections.abc import Mapping
from datetime import date, timedelta

import pytest

from it_activity.application.generate_profile import GenerateProfile, ProfileGenerationError
from it_activity.domain.activity import ActivityReport, DailyActivity
from it_activity.domain.profile import PUBLIC_OUTPUT_PATHS
from it_activity.domain.usage import UsageReport


class StaticActivityProvider:
    """Return a complete empty activity report."""

    def execute(self) -> ActivityReport:
        return ActivityReport(
            timezone="UTC",
            days=tuple(
                DailyActivity(date(2025, 8, 11) + timedelta(days=offset)) for offset in range(365)
            ),
        )


class StaticUsageProvider:
    """Return an empty public usage report."""

    def execute(self) -> UsageReport:
        return UsageReport(languages=(), technologies=())


class StubRenderer:
    """Return a configurable artifact mapping."""

    def __init__(self, rendered: Mapping[str, str]) -> None:
        self._rendered = rendered

    def render(self, activity: ActivityReport, usage: UsageReport) -> Mapping[str, str]:
        assert len(activity.days) == 365
        assert not usage.languages
        return self._rendered


class RecordingWriter:
    """Record whether public output was requested."""

    def __init__(self, changed: int) -> None:
        self._changed = changed
        self.calls = 0

    def write(self, artifacts: Mapping[str, str]) -> int:
        assert set(artifacts) == PUBLIC_OUTPUT_PATHS
        self.calls += 1
        return self._changed


def test_generate_profile_writes_complete_artifacts() -> None:
    writer = RecordingWriter(changed=3)
    renderer = StubRenderer({path: "content\n" for path in PUBLIC_OUTPUT_PATHS})

    result = GenerateProfile(
        StaticActivityProvider(),
        StaticUsageProvider(),
        renderer,
        writer,
    ).execute()

    assert result.changed_file_count == 3
    assert writer.calls == 1


def test_generate_profile_rejects_incomplete_render_before_write() -> None:
    writer = RecordingWriter(changed=0)
    renderer = StubRenderer({"README.md": "incomplete\n"})

    with pytest.raises(ProfileGenerationError, match="неполный"):
        GenerateProfile(
            StaticActivityProvider(),
            StaticUsageProvider(),
            renderer,
            writer,
        ).execute()

    assert writer.calls == 0


@pytest.mark.parametrize("changed", [-1, len(PUBLIC_OUTPUT_PATHS) + 1, True])
def test_generate_profile_rejects_invalid_writer_result(changed: int) -> None:
    writer = RecordingWriter(changed=changed)
    renderer = StubRenderer({path: "content\n" for path in PUBLIC_OUTPUT_PATHS})

    with pytest.raises(ProfileGenerationError, match="Filesystem adapter"):
        GenerateProfile(
            StaticActivityProvider(),
            StaticUsageProvider(),
            renderer,
            writer,
        ).execute()
