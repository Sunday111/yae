from __future__ import annotations

from pathlib import Path
import argparse
import os
import subprocess

from yae import git
from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.common import run_subprocess
from yae.errors import ProjectError
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class FormatCommand(Command):
    name = "format"
    help = "Apply clang-format to source files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--repository_dir",
            "--project_dir",
            dest="project_dir",
            type=Path,
            required=False,
            help="Path inside the Git repository to format",
        )
        parser.add_argument("--all", action="store_true", help="Format all tracked and untracked source files")
        parser.add_argument("--tool", default="clang-format", help="clang-format executable")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        requested_dir = context.log_project_dir()
        repository_root = git.run_git(requested_dir, ["rev-parse", "--show-toplevel"])
        if repository_root is None:
            raise ProjectError(
                f"Could not find a Git work tree containing {requested_dir}. "
                "Run this command from a Git repository or pass --repository_dir/--project_dir."
            )
        repository_dir = Path(repository_root).resolve()
        source_suffixes = {".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx"}
        files = sorted(
            file
            for file in self._get_files(repository_dir, args.all)
            if Path(file).suffix in source_suffixes and (repository_dir / file).is_file()
        )
        if files:
            scope = "source" if args.all else "changed source"
            logger.info("Formatting %d %s files", len(files), scope)
            run_subprocess([args.tool, "-i", "--", *files], cwd=repository_dir)
        else:
            scope = "source" if args.all else "changed source"
            logger.info("No %s files to format", scope)

    def _get_files(self, repository_dir: Path, format_all: bool) -> set[str]:
        if format_all:
            commands = [
                ["git", "ls-files", "-z"],
                ["git", "ls-files", "-z", "--others", "--exclude-standard"],
            ]
        else:
            commands = [
                ["git", "diff", "--name-only", "-z", "--diff-filter=ACMRTUXB"],
                ["git", "diff", "--name-only", "-z", "--diff-filter=ACMRTUXB", "--cached"],
                ["git", "ls-files", "-z", "--others", "--exclude-standard"],
            ]

        files: set[str] = set()
        for command in commands:
            output = subprocess.check_output(command, cwd=repository_dir)
            files.update(os.fsdecode(path) for path in output.split(b"\0") if path)
        return files
