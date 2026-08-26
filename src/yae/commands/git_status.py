from __future__ import annotations

from pathlib import Path
import argparse

from rich.console import Console

from yae import git
from yae import json_utils
from yae import yae_constants
from yae.errors import ProjectError
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
                raise ProjectError(
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

            push_note = self._push_note(repo)
            if not lines and push_note is None:
                if args.all:
                    console.print(f"[green]{label}[/] clean")
                    shown += 1
                continue

            parts = [f"[bold yellow]{label}[/]"]
            if lines:
                noun = "change" if len(lines) == 1 else "changes"
                parts.append(f"[dim]({len(lines)} {noun})[/]")
            if push_note is not None:
                parts.append(f"[cyan]({push_note})[/]")
            console.print(" ".join(parts))
            for line in lines:
                console.print(f"  {line}")
            shown += 1

        if shown == 0:
            console.print("No repositories with changes.")

    @staticmethod
    def _push_note(repo: Path) -> str | None:
        """A note about commits the remote does not have, or None when there is nothing to tell.

        Detached checkouts (dependencies pinned to tags) are not reported."""
        unpushed = git.unpushed_commit_count(repo)
        if unpushed is None:
            # A branch that never got an upstream is entirely unpushed; repositories
            # without remotes have nowhere to push to, so stay silent about them.
            if git.current_branch(repo) is not None and git.has_remotes(repo):
                return "branch has no upstream"
            return None
        if unpushed == 0:
            return None
        noun = "commit" if unpushed == 1 else "commits"
        return f"{unpushed} {noun} not pushed"

    def _collect_repos(
        self,
        project_dir: Path | None,
        cloned_repositories_dir: Path,
        registry_file: Path,
    ) -> list[tuple[str, Path]]:
        repos: list[tuple[str, Path]] = []
        seen: set[Path] = set()
        repositories_root = cloned_repositories_dir.resolve()

        def add(path: Path, require_contained: bool = False) -> None:
            resolved = path.resolve()
            if require_contained and not resolved.is_relative_to(repositories_root):
                return
            if resolved in seen:
                return
            seen.add(resolved)
            try:
                label = resolved.relative_to(repositories_root).as_posix()
            except ValueError:
                label = resolved.as_posix()
            repos.append((label, resolved))

        def child_directories(directory: Path) -> list[Path]:
            try:
                children = sorted(directory.iterdir())
            except OSError:
                return []
            return [child for child in children if not child.is_symlink() and child.is_dir()]

        if project_dir is not None:
            add(project_dir)

        if registry_file.is_file():
            registry = json_utils.read_json_file(registry_file)
            for local_path in sorted(registry.keys()):
                add(cloned_repositories_dir / local_path, require_contained=True)

        for owner_dir in child_directories(cloned_repositories_dir):
            for repository_dir in child_directories(owner_dir):
                for checkout_dir in child_directories(repository_dir):
                    git_marker = checkout_dir / ".git"
                    if not git_marker.is_symlink() and git_marker.exists():
                        add(checkout_dir, require_contained=True)

        return repos
