from __future__ import annotations

import argparse

from commands.base import Command
from commands.base import CommandContext
from commands.base import add_build_dir_argument
from commands.base import add_external_modules_dir_argument
from commands.base import add_project_dir_argument
from commands.common import get_build_dir_override
from commands.common import get_project_dir
from commands.common import run_cmake_configure


class ConfigureCommand(Command):
    name = "configure"
    help = "Configure CMake project"
    dependencies = ("generate",)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_external_modules_dir_argument(parser)
        add_build_dir_argument(parser)
        parser.add_argument("cmake_args", nargs=argparse.REMAINDER, help="Additional arguments passed to cmake")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        cmake_args = getattr(args, "cmake_args", [])
        if cmake_args and cmake_args[0] == "--":
            cmake_args = cmake_args[1:]

        run_cmake_configure(
            get_project_dir(args),
            get_build_dir_override(args),
            cmake_args,
        )
