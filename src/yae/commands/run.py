from __future__ import annotations

from pathlib import Path
import argparse
import os
import shutil

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_build_dir_argument
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import find_project_dir_by_run_target
from yae import yae_constants
from yae.commands.common import get_build_dir
from yae.commands.common import get_default_configuration
from yae.module import ModuleType
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class RunCommand(Command):
    name = "run"
    help = "Run the configured executable"
    dependencies = ("build",)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_cloned_repositories_dir_argument(parser)
        add_build_dir_argument(parser)
        parser.add_argument("run_target", nargs="?", help="Executable target to run instead of default run target")
        parser.add_argument("app_args", nargs=argparse.REMAINDER, help="Arguments passed to the executable")

    def validate(self, context: CommandContext, args: argparse.Namespace) -> None:
        # Runs before the "build" dependency, which otherwise fails with a cryptic
        # ninja error when asked to build a nonexistent or non-executable target.
        project_dir = self._resolve_project_dir(context, args)
        run_target = self._resolve_run_target(project_dir, args)
        module = context.resolve_project(project_dir).module_registry.find(run_target)
        if module is None or module.module_type != ModuleType.EXECUTABLE:
            raise SystemExit(
                f"'{run_target}' is not an executable module in {project_dir}. "
                f"Run 'yae list --executables' to see available run targets."
            )

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = self._resolve_project_dir(context, args)
        run_target = self._resolve_run_target(project_dir, args)

        app_args = args.app_args
        if app_args and app_args[0] == "--":
            app_args = app_args[1:]

        build_dir = get_build_dir(project_dir, context.build_dir_override)
        app_path = build_dir / yae_constants.RUNTIME_OUTPUT_SUBDIR / run_target
        logger.info("Running %s", app_path)
        self._run_with_discrete_gpu([app_path.as_posix(), *app_args])

    def _resolve_project_dir(self, context: CommandContext, args: argparse.Namespace) -> Path:
        project_dir = context.try_project_dir()
        if project_dir is not None:
            return project_dir

        run_target = getattr(args, "run_target", None)
        if run_target:
            cloned_repositories_dir = context.cloned_repositories_dir_for_discovery()
            if cloned_repositories_dir is not None:
                discovered = find_project_dir_by_run_target(cloned_repositories_dir, run_target)
                if discovered is not None:
                    # Pins the project on the shared context so the "build"/"configure"/
                    # "generate" dependencies in this invocation resolve to it too.
                    context.set_project_dir(discovered)
                    return discovered

        return context.project_dir()

    def _resolve_run_target(self, project_dir: Path, args: argparse.Namespace) -> str:
        default_configuration = get_default_configuration(project_dir)
        run_target = args.run_target or default_configuration.get("run_target")
        if not run_target:
            raise SystemExit("No run target was provided and default_configuration.run_target is not set")
        return run_target

    def _run_with_discrete_gpu(self, command: list[str]) -> None:
        if shutil.which("prime-run") is not None:
            logger.info("Using prime-run for NVIDIA GPU offload")
            os.execvp("prime-run", ["prime-run", *command])

        logger.info("Using NVIDIA PRIME environment variables")
        os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
        os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
        os.environ.setdefault("__VK_LAYER_NV_optimus", "NVIDIA_only")
        os.execv(command[0], command)
