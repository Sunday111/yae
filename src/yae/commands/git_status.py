from __future__ import annotations

from pathlib import Path
import argparse

from rich.console import Console

from yae import git
from yae import json_utils
from yae import yae_constants
from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.settings import ResolvedSettings


class GitStatusCommand(Command):
    name = "git-status"
    help = "Show git status for the project and its cloned repositories"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_cloned_repositories_dir_argument(parser)
        parser.add_argument("--all", action="store_true", help="Also list clean repositories and non-git paths")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = context.try_project_dir()
        if project_dir is not None:
            settings = ResolvedSettings.from_project(project_dir, context.cloned_repositories_dir_override)
            cloned_repositories_dir = settings.cloned_repositories_dir
            registry_file = settings.registry_file
        else:
            cloned_repositories_dir = context.cloned_repositories_dir_for_discovery()
            if cloned_repositories_dir is None:
                raise SystemExit(
                    "Could not find a project or a cloned repositories directory. Run this command from a YAE "
                    "project directory, pass --project_dir/--cloned_repositories_dir, or set "
                    "YAE_PROJECT_DIR/YAE_CLONED_REPOSITORIES_DIR."
                )
            registry_file = cloned_repositories_dir / yae_constants.REGISTRY_FILE_NAME

        repos = self._collect_repos(project_dir, cloned_repositories_dir, registry_file)

        console = Console()
        shown = 0
        for label, repo in repos:
            lines = git.status_short(repo)
            if lines is None:
                if args.all:
                    console.print(f"[yellow]{label}[/] [red](not a git repository)[/]")
                    shown += 1
                continue
            if not lines:
                if args.all:
                    console.print(f"[green]{label}[/] clean")
                    shown += 1
                continue

            noun = "change" if len(lines) == 1 else "changes"
            console.print(f"[bold yellow]{label}[/] [dim]({len(lines)} {noun})[/]")
            for line in lines:
                console.print(f"  {line}")
            shown += 1

        if shown == 0:
            console.print("No repositories with changes.")

    def _collect_repos(
        self,
        project_dir: Path | None,
        cloned_repositories_dir: Path,
        registry_file: Path,
    ) -> list[tuple[str, Path]]:
        repos: list[tuple[str, Path]] = []
        seen: set[Path] = set()

        def add(path: Path) -> None:
            resolved = path.resolve()
            if resolved in seen:
                return
            seen.add(resolved)
            try:
                label = resolved.relative_to(cloned_repositories_dir).as_posix()
            except ValueError:
                label = resolved.as_posix()
            repos.append((label, resolved))

        if project_dir is not None:
            add(project_dir)

        if registry_file.is_file():
            registry = json_utils.read_json_file(registry_file)
            for local_path in sorted(registry.keys()):
                add(cloned_repositories_dir / local_path)

        return repos
