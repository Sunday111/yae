from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import argparse


@dataclass(frozen=True)
class CommandContext:
    yae_root: Path


class Command:
    name: str
    help: str
    dependencies: Sequence[str] = ()

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        raise NotImplementedError


def add_project_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project_dir", type=Path, default=Path.cwd(), help="Path to directory with your project")


def add_build_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--build_dir", type=Path, required=False, help="Override build directory")


def add_external_modules_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--external_modules_dir",
        type=Path,
        required=False,
        help="Path to directory where external repositories live",
    )
