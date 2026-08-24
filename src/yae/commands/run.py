from __future__ import annotations

from pathlib import Path
import argparse
import os

from yae import yae_constants
from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_build_dir_argument
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import command_with_discrete_gpu
from yae.commands.common import find_project_dir_by_run_target
from yae.commands.common import get_build_dir
from yae.commands.common import get_default_configuration
from yae.errors import ProjectError
from yae.module import ModuleType
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class RunCommand(Command):
    name = "run"
    help = "Run the configured executable"
    dependencies = ("build",)
    wants_log = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_cloned_repositories_dir_argument(parser)
        add_build_dir_argument(parser)
        self._add_target_and_app_arguments(parser, "run")

    def validate(self, context: CommandContext, args: argparse.Namespace) -> None:
        self._normalize_target_and_app_arguments(args)
        # Runs before the "build" dependency, which otherwise fails with a cryptic
        # ninja error when asked to build a nonexistent or non-executable target.
        project_dir = self._resolve_project_dir(context, args)
        run_target = self._resolve_run_target(project_dir, args)
        module = context.resolve_project(project_dir).module_registry.find(run_target)
        if module is None or module.module_type != ModuleType.EXECUTABLE:
            raise ProjectError(
                f"'{run_target}' is not an executable module in {project_dir}. "
                f"Run 'yae list --executables' to see available run targets."
            )
        args.run_target = run_target

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        self._normalize_target_and_app_arguments(args)
        project_dir = self._resolve_project_dir(context, args)
        run_target = self._resolve_run_target(project_dir, args)

        app_args = args.app_args
        build_dir = get_build_dir(project_dir, context.build_dir_override)
        app_path = build_dir / yae_constants.RUNTIME_OUTPUT_SUBDIR / run_target
        logger.info("Running %s", app_path)
        command, environment = command_with_discrete_gpu([app_path.as_posix(), *app_args])
        os.execvpe(command[0], command, environment)

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
            raise ProjectError("No run target was provided and default_configuration.run_target is not set")
        return run_target

    def _add_target_and_app_arguments(self, parser: argparse.ArgumentParser, action: str) -> None:
        parser.add_argument(
            "target_and_app_args",
            nargs=argparse.REMAINDER,
            metavar="[target] [-- app args...]",
            help=f"Executable target to {action}, followed by arguments passed to it",
        )

    def _normalize_target_and_app_arguments(self, args: argparse.Namespace) -> None:
        tokens = getattr(args, "target_and_app_args", None)
        if tokens is None:
            return

        if "--" not in tokens:
            args.run_target = tokens[0] if tokens else None
            args.app_args = tokens[1:]
            args.target_and_app_args = None
            return

        separator = tokens.index("--")
        target = tokens[:separator]
        if len(target) > 1:
            raise ProjectError("Expected at most one executable target before '--'")
        args.run_target = target[0] if target else None
        args.app_args = tokens[separator + 1 :]
        args.target_and_app_args = None
