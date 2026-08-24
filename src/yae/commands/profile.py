from __future__ import annotations

from pathlib import Path
import argparse
import shutil
import sys

from yae import yae_constants
from yae.commands.base import CommandContext
from yae.commands.base import add_build_dir_argument
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import command_with_discrete_gpu
from yae.commands.common import get_build_dir
from yae.commands.common import run_subprocess
from yae.commands.run import RunCommand
from yae.errors import ProjectError
from yae.yae_logging import get_logger


logger = get_logger(__name__)

PERF_DATA_FILE_NAME = "perf.data"
SPEEDSCOPE_FILE_NAME = "profile.linux-perf.txt"


class ProfileCommand(RunCommand):
    name = "profile"
    help = "Profile an executable with perf and export it for Speedscope"
    dependencies = ("build",)
    wants_log = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_cloned_repositories_dir_argument(parser)
        add_build_dir_argument(parser)
        parser.add_argument("--output", type=Path, required=True, help="Directory for profile artifacts")
        parser.add_argument("--frequency", type=int, default=999, help="Samples per second")
        parser.add_argument("--event", default="cycles:u", help="perf event to sample")
        parser.add_argument("--call-graph", choices=("fp", "dwarf"), default="fp", help="Stack unwinding method")
        parser.add_argument("--perf", default="perf", help="perf executable")
        parser.add_argument("--overwrite", action="store_true", help="Replace existing profile files")
        self._add_target_and_app_arguments(parser, "profile")

    def validate(self, context: CommandContext, args: argparse.Namespace) -> None:
        if sys.platform != "linux":
            raise ProjectError("'yae profile' requires Linux perf")
        if shutil.which(args.perf) is None:
            raise ProjectError(f"Could not find perf executable '{args.perf}'")
        if args.frequency <= 0:
            raise ProjectError("--frequency must be positive")

        output = args.output.expanduser().resolve()
        if output.exists() and not output.is_dir():
            raise ProjectError(f"Profile output '{output}' is not a directory")
        if context.build_dir_override is None:
            context.set_build_dir(output / "build")

        existing = [path.name for path in self._profile_paths(output) if path.exists()]
        if existing and not args.overwrite:
            names = ", ".join(existing)
            raise ProjectError(f"Output already contains {names}; pass --overwrite to replace them")

        super().validate(context, args)

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        self._normalize_target_and_app_arguments(args)
        project_dir = self._resolve_project_dir(context, args)
        run_target = self._resolve_run_target(project_dir, args)
        build_dir = get_build_dir(project_dir, context.build_dir_override)
        application = build_dir / yae_constants.RUNTIME_OUTPUT_SUBDIR / run_target

        application_command, environment = command_with_discrete_gpu([application.as_posix(), *args.app_args])

        output = args.output.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        perf_data, speedscope_profile = self._profile_paths(output)
        if args.overwrite:
            for path in (perf_data, speedscope_profile):
                path.unlink(missing_ok=True)

        perf = shutil.which(args.perf)
        assert perf is not None
        run_subprocess(
            [
                perf,
                "record",
                "--output",
                perf_data.as_posix(),
                "--event",
                args.event,
                "--freq",
                str(args.frequency),
                "--call-graph",
                args.call_graph,
                "--",
                *application_command,
            ],
            env=environment,
        )
        logger.info("Exporting samples for Speedscope; symbolization may take a while")
        with speedscope_profile.open("w", encoding="utf-8") as output_file:
            run_subprocess([perf, "script", "--input", perf_data.as_posix()], stdout=output_file)
        logger.info("Speedscope profile: %s", speedscope_profile)

    def _profile_paths(self, output: Path) -> tuple[Path, Path]:
        return output / PERF_DATA_FILE_NAME, output / SPEEDSCOPE_FILE_NAME
