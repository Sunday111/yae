from __future__ import annotations

import argparse

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import run_project_file_generation


class GenerateCommand(Command):
    name = "generate"
    help = "Generate CMake project files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_cloned_repositories_dir_argument(parser)

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = context.project_dir()
        run_project_file_generation(
            project_dir,
            context.cloned_repositories_dir_override,
            show_clone_progress=context.show_clone_progress,
            resolved_project=context.resolve_project(project_dir),
        )
