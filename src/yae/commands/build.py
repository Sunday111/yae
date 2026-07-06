from __future__ import annotations

import argparse

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_build_dir_argument
from yae.commands.base import add_external_modules_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import get_build_dir
from yae.commands.common import get_build_dir_override
from yae.commands.common import get_default_configuration
from yae.commands.common import get_project_dir
from yae.commands.common import run_subprocess
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class BuildCommand(Command):
    name = "build"
    help = "Build CMake targets"
    dependencies = ("configure",)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_external_modules_dir_argument(parser)
        add_build_dir_argument(parser)
        parser.add_argument("targets", nargs="*", help="Targets to build instead of default build targets")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = get_project_dir(args)
        build_dir = get_build_dir(project_dir, get_build_dir_override(args))
        default_configuration = get_default_configuration(project_dir)

        targets = self._get_targets(args, default_configuration)
        if not targets:
            logger.info("Building default CMake target set")
            run_subprocess(["cmake", "--build", build_dir.as_posix(), "--parallel"])
            return

        for target in targets:
            logger.info("Building target %s", target)
            run_subprocess(["cmake", "--build", build_dir.as_posix(), "--target", target, "--parallel"])

    def _get_targets(self, args: argparse.Namespace, default_configuration: dict) -> list[str]:
        targets = getattr(args, "targets", None)
        if targets:
            return targets

        run_target = getattr(args, "run_target", None)
        if run_target:
            return [run_target]

        return default_configuration.get("build_targets", [])
