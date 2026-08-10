"""Command-line application assembly."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import Optional

from it_activity.adapters.credentials import EnvironmentGitHubTokenProvider
from it_activity.adapters.environment import EnvironmentConfigurationProvider
from it_activity.adapters.github import GitHubRestActivitySource
from it_activity.adapters.http import UrllibHttpClient
from it_activity.adapters.system_clock import SystemClock
from it_activity.application.collect_activity import CollectActivity, CollectionError
from it_activity.application.collect_usage import CollectUsage, UsageCollectionError
from it_activity.application.validate_configuration import ValidateConfiguration
from it_activity.domain.configuration import ConfigurationError
from it_activity.ports.activity_source import ActivitySourceError


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
        help="собрать обезличенные дневные агрегаты из GitHub",
    )
    subparsers.add_parser(
        "usage",
        help="собрать обезличенные языки и технологии из GitHub",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
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
            token = EnvironmentGitHubTokenProvider().load()
            activity_report = CollectActivity(
                configuration_provider=EnvironmentConfigurationProvider(),
                activity_source=GitHubRestActivitySource(UrllibHttpClient(), token),
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
            token = EnvironmentGitHubTokenProvider().load()
            usage_report = CollectUsage(
                configuration_provider=EnvironmentConfigurationProvider(),
                usage_source=GitHubRestActivitySource(UrllibHttpClient(), token),
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

    parser.error("Неизвестная команда.")
    return 2
