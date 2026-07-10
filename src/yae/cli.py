#!/usr/bin/env python3
"""Command-line entrypoint for yae."""

from pathlib import Path
import argparse
import os
import sys

from yae.commands import create_commands
from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.settings import PROJECT_DIR_ENV
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


def run_command(
    command: Command,
    commands_by_name: dict[str, Command],
    context: CommandContext,
    args: argparse.Namespace,
    completed_commands: set[str],
) -> None:
    if command.name in completed_commands:
        return

    command.validate(args)

    for dependency_name in command.dependencies:
        dependency = commands_by_name.get(dependency_name)
        if dependency is None:
            raise RuntimeError(f"Command {command.name} depends on unknown command {dependency_name}")
        run_command(dependency, commands_by_name, context, args, completed_commands)

    command.run(context, args)
    completed_commands.add(command.name)


def main() -> None:
    commands = create_commands()
    commands_by_name = {command.name: command for command in commands}
    parser = create_parser(commands)
    args = parser.parse_args(sys.argv[1:])

    if args.command is None:
        parser.print_help()
        return

    project_dir_arg = getattr(args, "project_dir", None)
    if project_dir_arg is not None:
        project_dir = project_dir_arg.resolve()
    elif project_dir_env := os.environ.get(PROJECT_DIR_ENV):
        project_dir = Path(project_dir_env).expanduser().resolve()
    else:
        project_dir = Path.cwd()
    configure_logging(verbose=args.verbose, log_path=project_dir / "yae.log")
    context = CommandContext()
    try:
        run_command(commands_by_name[args.command], commands_by_name, context, args, set())
    except Exception:
        logger.exception("Command failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
