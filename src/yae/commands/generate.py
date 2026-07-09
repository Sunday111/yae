from __future__ import annotations

import argparse

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_external_modules_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import get_project_dir
from yae.commands.common import run_project_file_generation


class GenerateCommand(Command):
    name = "generate"
    help = "Generate CMake project files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_external_modules_dir_argument(parser)

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        external_modules_dir_arg = getattr(args, "external_modules_dir", None)
        external_modules_dir = external_modules_dir_arg.resolve() if external_modules_dir_arg else None
        run_project_file_generation(
            get_project_dir(args),
            external_modules_dir,
            show_clone_progress=args.clone_progress,
        )
