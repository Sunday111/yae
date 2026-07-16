from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
import argparse
import os
import subprocess

from yae import git
from yae.commands.base import CommandContext
from yae.errors import ProjectError


CPP_FILE_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx"})
CPP_TRANSLATION_UNIT_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".cxx", ".cu"})


def add_repository_dir_argument(parser: argparse.ArgumentParser, action: str) -> None:
    parser.add_argument(
        "--repository_dir",
        "--project_dir",
        dest="project_dir",
        type=Path,
        required=False,
        help=f"Path inside the Git repository to {action}",
    )


def resolve_repository_dir(context: CommandContext) -> Path:
    requested_dir = context.log_project_dir()
    repository_root = git.run_git(requested_dir, ["rev-parse", "--show-toplevel"])
    if repository_root is None:
        raise ProjectError(
            f"Could not find a Git work tree containing {requested_dir}. "
            "Run this command from a Git repository or pass --repository_dir/--project_dir."
        )
    return Path(repository_root).resolve()


def collect_repository_files(
    repository_dir: Path,
    *,
    include_all: bool,
    suffixes: Collection[str],
) -> list[str]:
    if include_all:
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

    candidates: set[str] = set()
    for command in commands:
        output = subprocess.check_output(command, cwd=repository_dir)
        candidates.update(os.fsdecode(path) for path in output.split(b"\0") if path)

    return sorted(
        path
        for path in candidates
        if Path(path).suffix in suffixes and (repository_dir / path).is_file()
    )
