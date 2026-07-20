from __future__ import annotations

from pathlib import Path
import argparse

from yae import yae_constants
from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_build_dir_argument
from yae.commands.common import get_build_dir
from yae.commands.common import run_subprocess
from yae.commands.repository_files import CPP_TRANSLATION_UNIT_SUFFIXES
from yae.commands.repository_files import add_repository_dir_argument
from yae.commands.repository_files import collect_repository_files
from yae.commands.repository_files import resolve_repository_dir
from yae.errors import ProjectError
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class TidyCommand(Command):
    name = "tidy"
    help = "Run clang-tidy on source files"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_repository_dir_argument(parser, "check")
        add_build_dir_argument(parser)
        parser.add_argument("--all", action="store_true", help="Check all tracked and untracked translation units")
        parser.add_argument("--tool", default="clang-tidy", help="clang-tidy executable")
        parser.add_argument("tidy_args", nargs=argparse.REMAINDER, help="Additional arguments passed to clang-tidy")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        repository_dir = resolve_repository_dir(context)
        build_dir = self._get_build_dir(repository_dir, context.build_dir_override)
        compilation_database = build_dir / "compile_commands.json"
        if not compilation_database.is_file():
            raise ProjectError(
                f"Could not find a compilation database at {compilation_database}. "
                "Configure the project first or pass --build_dir."
            )

        files = collect_repository_files(
            repository_dir,
            include_all=args.all,
            suffixes=CPP_TRANSLATION_UNIT_SUFFIXES,
        )
        if not files:
            scope = "translation units" if args.all else "changed translation units"
            logger.info("No %s to check", scope)
            return

        tidy_args = list(getattr(args, "tidy_args", []))
        if tidy_args and tidy_args[0] == "--":
            tidy_args = tidy_args[1:]
        source_files = [(repository_dir / file).as_posix() for file in files]
        logger.info("Checking %d translation units", len(source_files))
        run_subprocess(
            [args.tool, f"-p={build_dir.as_posix()}", *source_files, *tidy_args],
            cwd=repository_dir,
        )

    @staticmethod
    def _get_build_dir(repository_dir: Path, build_dir_override: Path | None) -> Path:
        if build_dir_override is not None:
            return build_dir_override
        if (repository_dir / yae_constants.PROJECT_CONFIG_FILE_NAME).is_file():
            return get_build_dir(repository_dir, None)
        return repository_dir / yae_constants.DEFAULT_BUILD_DIR_NAME
