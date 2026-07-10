from __future__ import annotations

from pathlib import Path
from typing import Sequence
import argparse


class CommandContext:
    pass


class Command:
    name: str
    help: str
    dependencies: Sequence[str] = ()

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def validate(self, args: argparse.Namespace) -> None:
        """Checked before this command's dependencies run. Raise SystemExit to abort early."""

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        raise NotImplementedError


def add_project_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project_dir", type=Path, required=False, help="Path to directory with your project")


def add_build_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--build_dir", type=Path, required=False, help="Override build directory")


def add_cloned_repositories_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cloned_repositories_dir",
        type=Path,
        required=False,
        help="Path to directory where cloned repositories live",
    )
