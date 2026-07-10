from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from yae import yae_constants
from yae.local_config import read_local_config


CLONED_REPOSITORIES_DIR_ENV = "YAE_CLONED_REPOSITORIES_DIR"
PROJECT_DIR_ENV = "YAE_PROJECT_DIR"
LOCAL_CONFIG_CLONED_REPOSITORIES_DIR_KEY = "cloned_repositories_dir"


@dataclass(frozen=True)
class ResolvedSettings:
    project_root: Path
    cloned_repositories_dir: Path
    cloned_repositories_dir_source: str

    @classmethod
    def from_project(cls, project_root: Path, cli_cloned_repositories_dir: Path | None = None) -> "ResolvedSettings":
        project_root = project_root.resolve()
        candidates: list[tuple[Path, str]] = []

        if cli_cloned_repositories_dir is not None:
            candidates.append((cli_cloned_repositories_dir, "cli"))

        if local_value := _read_local_cloned_repositories_dir(project_root):
            candidates.append((_resolve_project_path(project_root, local_value), "local-config"))

        if env_value := os.environ.get(CLONED_REPOSITORIES_DIR_ENV):
            candidates.append((Path(env_value), "environment"))

        candidates.append((project_root / yae_constants.CLONED_REPOSITORIES_DIRECTORY_NAME, "default"))

        cloned_repositories_dir, source = candidates[0]
        if not cloned_repositories_dir.is_absolute():
            cloned_repositories_dir = _resolve_project_path(project_root, cloned_repositories_dir.as_posix())
        return cls(
            project_root=project_root,
            cloned_repositories_dir=cloned_repositories_dir,
            cloned_repositories_dir_source=source,
        )

    @property
    def default_cloned_repositories_dir(self) -> Path:
        return self.project_root / yae_constants.CLONED_REPOSITORIES_DIRECTORY_NAME

    @property
    def registry_file(self) -> Path:
        return self.cloned_repositories_dir / "registry.json"


def _read_local_cloned_repositories_dir(project_root: Path) -> str | None:
    local_config = read_local_config(project_root)
    if value := local_config.get(LOCAL_CONFIG_CLONED_REPOSITORIES_DIR_KEY):
        return str(value)

    local_default_configuration = local_config.get("default_configuration", {})
    if value := local_default_configuration.get(LOCAL_CONFIG_CLONED_REPOSITORIES_DIR_KEY):
        return str(value)

    return None


def _resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path
