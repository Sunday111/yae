from __future__ import annotations

import argparse
import subprocess

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_project_dir_argument
from yae.commands.common import run_subprocess
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class CleanupCommand(Command):
    name = "cleanup"
    help = "Re-sync submodules and delete ignored files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = context.project_dir()
        has_submodules = subprocess.run(
            ["git", "config", "--file", ".gitmodules", "--get-regexp", "path"],
            cwd=project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if has_submodules:
            logger.info("Recloning submodules")
            run_subprocess(["git", "submodule", "deinit", "--force", "--all"], cwd=project_dir)
            run_subprocess(["git", "submodule", "sync", "--recursive"], cwd=project_dir)
            run_subprocess(["git", "submodule", "update", "--init", "--recursive"], cwd=project_dir)
        logger.info("Deleting gitignored files")
        run_subprocess(["git", "clean", "-ffdX"], cwd=project_dir)
