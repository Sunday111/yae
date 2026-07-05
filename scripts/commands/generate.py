from __future__ import annotations

import argparse

from commands.base import Command
from commands.base import CommandContext
from commands.base import add_external_modules_dir_argument
from commands.base import add_project_dir_argument
from commands.common import get_project_dir
from commands.common import run_project_file_generation


class GenerateCommand(Command):
    name = "generate"
    help = "Generate CMake project files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_external_modules_dir_argument(parser)

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        external_modules_dir_arg = getattr(args, "external_modules_dir", None)
        external_modules_dir = external_modules_dir_arg.resolve() if external_modules_dir_arg else None
        run_project_file_generation(context.yae_root, get_project_dir(args), external_modules_dir)
