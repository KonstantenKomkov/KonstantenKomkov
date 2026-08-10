"""Command-line application assembly."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from it_activity.adapters.composite_activity import CompositeActivitySource
from it_activity.adapters.composite_github import CompositeGitHubActivitySource
from it_activity.adapters.credentials import EnvironmentGitHubTokensProvider
from it_activity.adapters.environment import EnvironmentConfigurationProvider
from it_activity.adapters.filesystem import FilesystemPublicOutputWriter
from it_activity.adapters.github import GitHubRestActivitySource
from it_activity.adapters.http import UrllibHttpClient
from it_activity.adapters.local_git import (
    EnvironmentLocalRepositoryPathsProvider,
    LocalGitActivitySource,
)
from it_activity.adapters.svg_renderer import SvgProfileRenderer
from it_activity.adapters.system_clock import SystemClock
from it_activity.application.collect_activity import CollectActivity, CollectionError
from it_activity.application.collect_usage import CollectUsage, UsageCollectionError
from it_activity.application.generate_profile import GenerateProfile, ProfileGenerationError
from it_activity.application.validate_configuration import ValidateConfiguration
from it_activity.domain.configuration import ConfigurationError
from it_activity.ports.activity_source import ActivitySource, ActivitySourceError
from it_activity.ports.configuration import ConfigurationProvider
from it_activity.ports.output import PublicOutputError
from it_activity.ports.rendering import ProfileRenderingError


def _build_github_source() -> CompositeGitHubActivitySource:
    """Build one private-safe source from every independently scoped token."""
    http_client = UrllibHttpClient()
    return CompositeGitHubActivitySource(
        tuple(
            GitHubRestActivitySource(http_client, token)
            for token in EnvironmentGitHubTokensProvider().load()
        )
    )


def _with_optional_local_activity(
    github_source: CompositeGitHubActivitySource,
) -> tuple[ActivitySource, ConfigurationProvider]:
    """Extend GitHub activity with local clones configured only at runtime."""
    repository_paths = EnvironmentLocalRepositoryPathsProvider().load()
    if not repository_paths:
        return github_source, EnvironmentConfigurationProvider()

    local_source = LocalGitActivitySource(repository_paths)
    return (
        CompositeActivitySource((github_source, local_source)),
        EnvironmentConfigurationProvider(
            additional_expected_repositories=local_source.repository_names
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser without invoking external adapters."""
    parser = argparse.ArgumentParser(
        prog="it-activity",
        description="Агрегация активности GitHub без раскрытия приватных данных.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "validate-config",
        help="проверить конфигурацию и вывести только публичную сводку",
    )
    subparsers.add_parser(
        "collect",
        help="собрать обезличенные дневные агрегаты из настроенных источников",
    )
    subparsers.add_parser(
        "usage",
        help="собрать обезличенные языки и технологии из GitHub",
    )
    subparsers.add_parser(
        "generate",
        help="собрать и записать полный профильный README и SVG",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit status."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command is None:
        parser.print_help()
        return 0

    if arguments.command == "validate-config":
        try:
            summary = ValidateConfiguration(EnvironmentConfigurationProvider()).execute()
        except ConfigurationError as error:
            print(f"Ошибка конфигурации: {error}", file=sys.stderr)
            return 2
        print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))
        return 0

    if arguments.command == "collect":
        try:
            github_source = _build_github_source()
            activity_source, activity_configuration_provider = _with_optional_local_activity(
                github_source
            )
            activity_report = CollectActivity(
                configuration_provider=activity_configuration_provider,
                activity_source=activity_source,
                clock=SystemClock(),
            ).execute()
        except (ActivitySourceError, CollectionError, ConfigurationError) as error:
            print(f"Ошибка сбора: {error}", file=sys.stderr)
            return 1
        except Exception:
            print("Ошибка сбора: непредвиденный внутренний сбой.", file=sys.stderr)
            return 1
        public_days = [
            {
                "added_lines": day.added_lines,
                "commits": day.commits,
                "date": day.day.isoformat(),
                "deleted_lines": day.deleted_lines,
            }
            for day in activity_report.days
        ]
        print(
            json.dumps(
                {"days": public_days, "timezone": activity_report.timezone},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if arguments.command == "usage":
        try:
            usage_report = CollectUsage(
                configuration_provider=EnvironmentConfigurationProvider(),
                usage_source=_build_github_source(),
            ).execute()
        except (ActivitySourceError, ConfigurationError, UsageCollectionError) as error:
            print(f"Ошибка сбора: {error}", file=sys.stderr)
            return 1
        except Exception:
            print("Ошибка сбора: непредвиденный внутренний сбой.", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "languages": [asdict(language) for language in usage_report.languages],
                    "technologies": [
                        asdict(technology) for technology in usage_report.technologies
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if arguments.command == "generate":
        try:
            configuration_provider = EnvironmentConfigurationProvider()
            github_source = _build_github_source()
            activity_source, activity_configuration_provider = _with_optional_local_activity(
                github_source
            )
            result = GenerateProfile(
                activity_provider=CollectActivity(
                    configuration_provider=activity_configuration_provider,
                    activity_source=activity_source,
                    clock=SystemClock(),
                ),
                usage_provider=CollectUsage(
                    configuration_provider=configuration_provider,
                    usage_source=github_source,
                ),
                renderer=SvgProfileRenderer(),
                output_writer=FilesystemPublicOutputWriter(Path.cwd()),
            ).execute()
        except (
            ActivitySourceError,
            CollectionError,
            ConfigurationError,
            ProfileGenerationError,
            ProfileRenderingError,
            PublicOutputError,
            UsageCollectionError,
        ) as error:
            print(f"Ошибка генерации: {error}", file=sys.stderr)
            return 1
        except Exception:
            print("Ошибка генерации: непредвиденный внутренний сбой.", file=sys.stderr)
            return 1
        print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
        return 0

    parser.error("Неизвестная команда.")
    return 2
