from __future__ import annotations

from pathlib import Path
import argparse
import subprocess

from commands.base import Command
from commands.base import CommandContext
from commands.base import add_project_dir_argument
from commands.common import get_project_dir


class FormatCommand(Command):
    name = "format"
    help = "Apply clang-format to changed source files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        parser.add_argument("--tool", default="clang-format", help="clang-format executable")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = get_project_dir(args)
        commands = [
            ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"],
            ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "--cached"],
            ["git", "ls-files", "--others", "--exclude-standard"],
        ]
        changed_files: set[str] = set()
        for command in commands:
            output = subprocess.check_output(command, cwd=project_dir, text=True)
            changed_files.update(line for line in output.splitlines() if line)

        source_suffixes = {".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx"}
        files = sorted(file for file in changed_files if Path(file).suffix in source_suffixes)
        if files:
            subprocess.check_call([args.tool, "-i", "--", *files], cwd=project_dir)
