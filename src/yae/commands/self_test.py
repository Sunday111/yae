from __future__ import annotations

from pathlib import Path
import argparse

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.tests.self_test import run_self_test


class SelfTestCommand(Command):
    name = "self-test"
    help = "Run YAE's built-in self-test fixture"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--yae-root",
            type=Path,
            default=Path(__file__).resolve().parents[3],
            help="Path to the YAE checkout containing tests/fixtures",
        )

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        run_self_test(args.yae_root.resolve())
