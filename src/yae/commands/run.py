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
from yae.commands.common import find_executable_module
from yae.commands.common import find_project_dir_by_run_target
from yae.commands.common import get_build_dir
from yae.commands.common import get_build_dir_override
from yae.commands.common import get_cloned_repositories_dir_for_discovery
from yae.commands.common import get_cloned_repositories_dir_override
from yae.commands.common import get_default_configuration
from yae.commands.common import get_project_dir
from yae.commands.common import try_get_project_dir
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

    def validate(self, args: argparse.Namespace) -> None:
        # Runs before the "build" dependency, which otherwise fails with a cryptic
        # ninja error when asked to build a nonexistent or non-executable target.
        project_dir = self._resolve_project_dir(args)
        run_target = self._resolve_run_target(project_dir, args)
        cloned_repositories_dir = get_cloned_repositories_dir_override(args)
        module = find_executable_module(
            project_dir,
            cloned_repositories_dir,
            run_target,
            show_clone_progress=args.clone_progress,
        )
        if module is None:
            raise SystemExit(
                f"'{run_target}' is not an executable module in {project_dir}. "
                f"Run 'yae list --executables' to see available run targets."
            )

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = self._resolve_project_dir(args)
        run_target = self._resolve_run_target(project_dir, args)

        app_args = args.app_args
        if app_args and app_args[0] == "--":
            app_args = app_args[1:]

        build_dir = get_build_dir(project_dir, get_build_dir_override(args))
        app_path = build_dir / "bin" / run_target
        logger.info("Running %s", app_path)
        self._run_with_discrete_gpu([app_path.as_posix(), *app_args])

    def _resolve_project_dir(self, args: argparse.Namespace) -> Path:
        project_dir = try_get_project_dir(args)
        if project_dir is not None:
            return project_dir

        run_target = getattr(args, "run_target", None)
        if run_target:
            cloned_repositories_dir = get_cloned_repositories_dir_for_discovery(args)
            if cloned_repositories_dir is not None:
                discovered = find_project_dir_by_run_target(cloned_repositories_dir, run_target)
                if discovered is not None:
                    # Shared with the "build"/"configure"/"generate" dependencies that
                    # run against this same args namespace before RunCommand.run().
                    args.project_dir = discovered
                    return discovered

        return get_project_dir(args)

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
