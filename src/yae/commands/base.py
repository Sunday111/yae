from __future__ import annotations

from pathlib import Path
from typing import Sequence
import argparse
import os

from yae.resolver import ResolvedProject
from yae.resolver import resolve_project
from yae.settings import CLONED_REPOSITORIES_DIR_ENV
from yae.settings import PROJECT_DIR_ENV


def _resolved_path(value: object) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()  # type: ignore[arg-type]


class CommandContext:
    """Resolved execution inputs, computed once from args + environment.

    Commands read the project directory, cloned-repositories directory and clone
    progress from here instead of re-deriving them from the argparse namespace,
    and share a single resolution cache for the whole invocation.
    """

    def __init__(
        self,
        *,
        project_dir_override: Path | None,
        project_dir_env: Path | None,
        cloned_repositories_dir_override: Path | None,
        cloned_repositories_dir_env: Path | None,
        build_dir_override: Path | None,
        show_clone_progress: bool,
    ) -> None:
        self._project_dir_override = project_dir_override
        self._project_dir_env = project_dir_env
        self._cloned_repositories_dir_override = cloned_repositories_dir_override
        self._cloned_repositories_dir_env = cloned_repositories_dir_env
        self._build_dir_override = build_dir_override
        self.show_clone_progress = show_clone_progress
        self._resolved_project_dir: Path | None = None
        self._resolution_cache: dict[Path, ResolvedProject] = {}

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "CommandContext":
        return cls(
            project_dir_override=_resolved_path(getattr(args, "project_dir", None)),
            project_dir_env=_resolved_path(os.environ.get(PROJECT_DIR_ENV)),
            cloned_repositories_dir_override=_resolved_path(getattr(args, "cloned_repositories_dir", None)),
            cloned_repositories_dir_env=_resolved_path(os.environ.get(CLONED_REPOSITORIES_DIR_ENV)),
            build_dir_override=_resolved_path(getattr(args, "build_dir", None)),
            show_clone_progress=bool(getattr(args, "clone_progress", False)),
        )

    @property
    def _project_dir_candidate(self) -> Path:
        if self._project_dir_override is not None:
            return self._project_dir_override
        if self._project_dir_env is not None:
            return self._project_dir_env
        return Path.cwd().resolve()

    def log_project_dir(self) -> Path:
        """Best-effort directory for the log file; does not require a project to exist."""
        return self._project_dir_candidate

    def try_project_dir(self) -> Path | None:
        """The resolved project directory, or None if none was found."""
        if self._resolved_project_dir is not None:
            return self._resolved_project_dir
        candidate = self._project_dir_candidate
        return candidate if (candidate / "yae_project.json").is_file() else None

    def project_dir(self) -> Path:
        """The resolved project directory, or exit with a clear error."""
        found = self.try_project_dir()
        if found is None:
            raise SystemExit(
                f"Could not find yae_project.json in {self._project_dir_candidate}. "
                f"Run this command from a YAE project directory, pass --project_dir, or set {PROJECT_DIR_ENV}."
            )
        return found

    def set_project_dir(self, project_dir: Path) -> None:
        """Pins the project directory (e.g. after `yae run <target>` discovers one),
        so dependent commands in the same invocation resolve to it too."""
        self._resolved_project_dir = project_dir

    @property
    def cloned_repositories_dir_override(self) -> Path | None:
        """The --cloned_repositories_dir override, if any (env/local-config are applied later
        by ResolvedSettings, which needs a project root)."""
        return self._cloned_repositories_dir_override

    def cloned_repositories_dir_for_discovery(self) -> Path | None:
        """A cloned-repositories root usable without a project: the CLI override or the
        environment variable."""
        if self._cloned_repositories_dir_override is not None:
            return self._cloned_repositories_dir_override
        return self._cloned_repositories_dir_env

    @property
    def build_dir_override(self) -> Path | None:
        return self._build_dir_override

    def resolve_project(self, project_dir: Path) -> ResolvedProject:
        """Resolves a project once per invocation; repeated calls for the same directory
        (e.g. `run`'s validation and its `generate` dependency) reuse the cached result."""
        key = project_dir.resolve()
        if key not in self._resolution_cache:
            self._resolution_cache[key] = resolve_project(
                project_dir=project_dir,
                cloned_repositories_dir=self._cloned_repositories_dir_override,
                show_clone_progress=self.show_clone_progress,
            )
        return self._resolution_cache[key]


class Command:
    name: str
    help: str
    dependencies: Sequence[str] = ()

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def validate(self, context: CommandContext, args: argparse.Namespace) -> None:
        """Checked before this command's dependencies run. Raise SystemExit to abort early."""

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        raise NotImplementedError


def add_project_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project_dir", type=Path, required=False, help="Path to directory with your project")


def add_build_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--build_dir", type=Path, required=False, help="Override build directory")


def add_cloned_repositories_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cloned_repositories_dir",
        type=Path,
        required=False,
        help="Path to directory where cloned repositories live",
    )
