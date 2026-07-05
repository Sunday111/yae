from __future__ import annotations

import argparse
import subprocess

from commands.base import Command
from commands.base import CommandContext
from commands.base import add_build_dir_argument
from commands.base import add_external_modules_dir_argument
from commands.base import add_project_dir_argument
from commands.common import get_build_dir
from commands.common import get_build_dir_override
from commands.common import get_default_configuration
from commands.common import get_project_dir


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
            subprocess.check_call(["cmake", "--build", build_dir.as_posix(), "--parallel"])
            return

        for target in targets:
            subprocess.check_call(["cmake", "--build", build_dir.as_posix(), "--target", target, "--parallel"])

    def _get_targets(self, args: argparse.Namespace, default_configuration: dict) -> list[str]:
        targets = getattr(args, "targets", None)
        if targets:
            return targets

        run_target = getattr(args, "run_target", None)
        if run_target:
            result = [run_target]
            if copy_target := default_configuration.get("run_copy_target"):
                result.append(copy_target)
            return result

        return default_configuration.get("build_targets", [])
