from __future__ import annotations

from pathlib import Path
import argparse
import os
import shutil

from commands.base import Command
from commands.base import CommandContext
from commands.base import add_build_dir_argument
from commands.base import add_external_modules_dir_argument
from commands.base import add_project_dir_argument
from commands.common import get_build_dir
from commands.common import get_build_dir_override
from commands.common import get_default_configuration
from commands.common import get_project_dir


class RunCommand(Command):
    name = "run"
    help = "Run the configured executable"
    dependencies = ("build",)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_external_modules_dir_argument(parser)
        add_build_dir_argument(parser)
        parser.add_argument("run_target", nargs="?", help="Executable target to run instead of default run target")
        parser.add_argument("app_args", nargs=argparse.REMAINDER, help="Arguments passed to the executable")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = get_project_dir(args)
        default_configuration = get_default_configuration(project_dir)
        run_target = args.run_target or default_configuration.get("run_target")
        if not run_target:
            raise SystemExit("No run target was provided and default_configuration.run_target is not set")

        app_args = args.app_args
        if app_args and app_args[0] == "--":
            app_args = app_args[1:]

        build_dir = get_build_dir(project_dir, get_build_dir_override(args))
        app_path = build_dir / "bin" / run_target
        self._run_with_discrete_gpu([app_path.as_posix(), *app_args])

    def _run_with_discrete_gpu(self, command: list[str]) -> None:
        if shutil.which("prime-run") is not None:
            os.execvp("prime-run", ["prime-run", *command])

        os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
        os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
        os.environ.setdefault("__VK_LAYER_NV_optimus", "NVIDIA_only")
        os.execv(command[0], command)
