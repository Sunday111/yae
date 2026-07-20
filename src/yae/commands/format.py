from __future__ import annotations

import argparse

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.common import run_subprocess
from yae.commands.repository_files import CPP_FILE_SUFFIXES
from yae.commands.repository_files import add_repository_dir_argument
from yae.commands.repository_files import collect_repository_files
from yae.commands.repository_files import resolve_repository_dir
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class FormatCommand(Command):
    name = "format"
    help = "Apply clang-format to source files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_repository_dir_argument(parser, "format")
        parser.add_argument("--all", action="store_true", help="Format all tracked and untracked source files")
        parser.add_argument("--tool", default="clang-format", help="clang-format executable")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        repository_dir = resolve_repository_dir(context)
        files = collect_repository_files(
            repository_dir,
            include_all=args.all,
            suffixes=CPP_FILE_SUFFIXES,
        )
        if files:
            scope = "source" if args.all else "changed source"
            logger.info("Formatting %d %s files", len(files), scope)
            run_subprocess([args.tool, "-i", "--", *files], cwd=repository_dir)
        else:
            scope = "source" if args.all else "changed source"
            logger.info("No %s files to format", scope)
