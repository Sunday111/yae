from __future__ import annotations

import argparse
import os

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_build_dir_argument
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import get_build_dir
from yae.commands.common import run_subprocess
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class TestCommand(Command):
    name = "test"
    help = "Build the project and run its tests with ctest"
    # Chains configure -> generate. `run()` then builds the WHOLE project before
    # ctest (equivalent to `cmake --build <build> && ctest`); building every target
    # rather than just the default set is what keeps ctest from reporting the
    # registered-but-unbuilt sibling test modules as NOT_BUILT failures.
    dependencies = ("configure",)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_cloned_repositories_dir_argument(parser)
        add_build_dir_argument(parser)
        parser.add_argument(
            "-j",
            "--jobs",
            type=int,
            default=os.cpu_count() or 1,
            help="Number of tests to run in parallel (default: CPU count)",
        )
        parser.add_argument(
            "-R",
            "--tests-regex",
            dest="tests_regex",
            default=None,
            help="Only run tests whose name matches this regular expression (ctest -R)",
        )

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = context.project_dir()
        build_dir = get_build_dir(project_dir, context.build_dir_override)

        logger.info("Building project in %s", build_dir)
        run_subprocess(["cmake", "--build", build_dir.as_posix(), "--parallel"])

        command = [
            "ctest",
            "--test-dir",
            build_dir.as_posix(),
            "--output-on-failure",
            "-j",
            str(args.jobs),
        ]
        if args.tests_regex:
            command.extend(["-R", args.tests_regex])

        logger.info("Running tests in %s", build_dir)
        run_subprocess(command)
