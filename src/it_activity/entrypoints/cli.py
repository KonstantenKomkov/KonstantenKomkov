"""Command-line application assembly."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import Optional

from it_activity.adapters.environment import EnvironmentConfigurationProvider
from it_activity.application.validate_configuration import ValidateConfiguration
from it_activity.domain.configuration import ConfigurationError


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

    parser.error("Неизвестная команда.")
    return 2
