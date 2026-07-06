from __future__ import annotations

from pathlib import Path
import argparse
import subprocess

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_project_dir_argument
from yae.commands.common import get_project_dir
from yae.commands.common import run_subprocess
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class FormatCommand(Command):
    name = "format"
    help = "Apply clang-format to source files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        parser.add_argument("--all", action="store_true", help="Format all tracked and untracked source files")
        parser.add_argument("--tool", default="clang-format", help="clang-format executable")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = get_project_dir(args)
        source_suffixes = {".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx"}
        files = sorted(file for file in self._get_files(project_dir, args.all) if Path(file).suffix in source_suffixes)
        if files:
            scope = "source" if args.all else "changed source"
            logger.info("Formatting %d %s files", len(files), scope)
            run_subprocess([args.tool, "-i", "--", *files], cwd=project_dir)
        else:
            scope = "source" if args.all else "changed source"
            logger.info("No %s files to format", scope)

    def _get_files(self, project_dir: Path, format_all: bool) -> set[str]:
        if format_all:
            commands = [
                ["git", "ls-files"],
                ["git", "ls-files", "--others", "--exclude-standard"],
            ]
        else:
            commands = [
                ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"],
                ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "--cached"],
                ["git", "ls-files", "--others", "--exclude-standard"],
            ]

        files: set[str] = set()
        for command in commands:
            output = subprocess.check_output(command, cwd=project_dir, text=True)
            files.update(line for line in output.splitlines() if line)
        return files
