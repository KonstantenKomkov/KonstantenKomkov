"""Use case for collecting and publishing the complete profile output."""

from dataclasses import dataclass
from typing import Protocol

from it_activity.domain.activity import ActivityReport
from it_activity.domain.profile import PUBLIC_OUTPUT_PATHS
from it_activity.domain.usage import UsageReport
from it_activity.ports.output import PublicOutputWriter
from it_activity.ports.rendering import ProfileRenderer


class ActivityReportProvider(Protocol):
    """Provide a complete daily activity report."""

    def execute(self) -> ActivityReport:
        """Return the report."""


class UsageReportProvider(Protocol):
    """Provide a complete language and technology report."""

    def execute(self) -> UsageReport:
        """Return the report."""


class ProfileGenerationError(RuntimeError):
    """A safe failure that prevents profile publication."""


@dataclass(frozen=True)
class GenerationResult:
    """Public-only result of writing generated profile files."""

    changed_file_count: int


class GenerateProfile:
    """Collect, render, validate, and publish all profile artifacts."""

    def __init__(
        self,
        activity_provider: ActivityReportProvider,
        usage_provider: UsageReportProvider,
        renderer: ProfileRenderer,
        output_writer: PublicOutputWriter,
    ) -> None:
        self._activity_provider = activity_provider
        self._usage_provider = usage_provider
        self._renderer = renderer
        self._output_writer = output_writer

    def execute(self) -> GenerationResult:
        """Write output only when collection and rendering are fully complete."""
        activity = self._activity_provider.execute()
        usage = self._usage_provider.execute()
        artifacts = self._renderer.render(activity, usage)
        if set(artifacts) != PUBLIC_OUTPUT_PATHS:
            raise ProfileGenerationError("Renderer вернул неполный набор публичных файлов.")
        if any(not isinstance(content, str) or not content for content in artifacts.values()):
            raise ProfileGenerationError("Renderer вернул некорректный публичный файл.")
        changed_file_count = self._output_writer.write(artifacts)
        if (
            not isinstance(changed_file_count, int)
            or isinstance(changed_file_count, bool)
            or changed_file_count < 0
            or changed_file_count > len(PUBLIC_OUTPUT_PATHS)
        ):
            raise ProfileGenerationError("Filesystem adapter вернул некорректный результат.")
        return GenerationResult(changed_file_count=changed_file_count)
