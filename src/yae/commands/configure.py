from __future__ import annotations

import argparse

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_build_dir_argument
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import get_build_dir_override
from yae.commands.common import get_cloned_repositories_dir_override
from yae.commands.common import get_project_dir
from yae.commands.common import run_cmake_configure


class ConfigureCommand(Command):
    name = "configure"
    help = "Configure CMake project"
    dependencies = ("generate",)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_cloned_repositories_dir_argument(parser)
        add_build_dir_argument(parser)
        parser.add_argument("cmake_args", nargs=argparse.REMAINDER, help="Additional arguments passed to cmake")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        cmake_args = getattr(args, "cmake_args", [])
        if cmake_args and cmake_args[0] == "--":
            cmake_args = cmake_args[1:]

        run_cmake_configure(
            get_project_dir(args),
            get_cloned_repositories_dir_override(args),
            get_build_dir_override(args),
            cmake_args,
        )
