from __future__ import annotations

import argparse
import subprocess

from commands.base import Command
from commands.base import CommandContext
from commands.base import add_project_dir_argument
from commands.common import get_project_dir


class CleanupCommand(Command):
    name = "cleanup"
    help = "Re-sync submodules and delete ignored files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = get_project_dir(args)
        has_submodules = subprocess.run(
            ["git", "config", "--file", ".gitmodules", "--get-regexp", "path"],
            cwd=project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if has_submodules:
            subprocess.check_call(["git", "submodule", "deinit", "--force", "--all"], cwd=project_dir)
            subprocess.check_call(["git", "submodule", "sync", "--recursive"], cwd=project_dir)
            subprocess.check_call(["git", "submodule", "update", "--init", "--recursive"], cwd=project_dir)
        subprocess.check_call(["git", "clean", "-ffdX"], cwd=project_dir)
