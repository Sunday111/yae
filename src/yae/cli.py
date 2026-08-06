#!/usr/bin/env python3
"""Command-line entrypoint for yae."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

from yae.commands import create_commands
from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.errors import YaeError
from yae.yae_logging import configure_logging
from yae.yae_logging import get_logger


logger = get_logger(__name__)


def create_parser(commands: list[Command]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yae")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose yae diagnostics")
    parser.add_argument("--clone-progress", action="store_true", help="Show git clone progress while fetching repositories")
    subparsers = parser.add_subparsers(dest="command")

    for command in commands:
        subparser = subparsers.add_parser(command.name, help=command.help, description=command.help)
        command.add_arguments(subparser)

    return parser


def execution_list(command: Command, commands_by_name: dict[str, Command]) -> list[Command]:
    """Everything the command needs run, dependencies before dependents."""
    ordered: list[Command] = []
    visited: set[str] = set()

    def visit(current: Command) -> None:
        if current.name in visited:
            return
        visited.add(current.name)

        for dependency_name in current.dependencies:
            dependency = commands_by_name.get(dependency_name)
            if dependency is None:
                raise RuntimeError(f"Command {current.name} depends on unknown command {dependency_name}")
            visit(dependency)

        ordered.append(current)

    visit(command)
    return ordered


def run_commands(commands: list[Command], context: CommandContext, args: argparse.Namespace) -> None:
    # Everything is checked before anything runs, so a run that cannot finish
    # does not get half way first.
    for command in reversed(commands):
        command.validate(context, args)

    for command in commands:
        command.run(context, args)


def log_path(context: CommandContext, commands: list[Command]) -> Path | None:
    """Where this invocation keeps its log, or nowhere when none of the commands
    about to run asked for one."""
    if not any(command.wants_log for command in commands):
        return None
    return context.log_project_dir() / "yae.log"


def main() -> None:
    commands = create_commands()
    commands_by_name = {command.name: command for command in commands}
    parser = create_parser(commands)
    args = parser.parse_args(sys.argv[1:])

    if args.command is None:
        parser.print_help()
        return

    context = CommandContext.from_args(args)
    plan = execution_list(commands_by_name[args.command], commands_by_name)
    configure_logging(verbose=args.verbose, log_path=log_path(context, plan))
    try:
        run_commands(plan, context, args)
    except YaeError as error:
        # Expected failure: a single clean message, no traceback.
        logger.error("%s", error)
        raise SystemExit(1)
    except Exception:
        # Unexpected failure: surface the full traceback.
        logger.exception("Command failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
