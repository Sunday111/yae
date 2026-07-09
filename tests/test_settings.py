from __future__ import annotations

import json
from pathlib import Path

from yae.settings import CLONED_REPOSITORIES_DIR_ENV
from yae.settings import ResolvedSettings


def write_project(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "yae_project.json").write_text(
        json.dumps({"name": "TestProject", "cpp": {"standard": "20"}}),
        encoding="utf-8",
    )


def test_cloned_repositories_dir_precedence(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)

    cli_dir = tmp_path / "cli"
    local_dir = tmp_path / "local"
    env_dir = tmp_path / "env"

    monkeypatch.delenv(CLONED_REPOSITORIES_DIR_ENV, raising=False)
    assert ResolvedSettings.from_project(project_dir).cloned_repositories_dir == project_dir / "cloned_repositories"

    monkeypatch.setenv(CLONED_REPOSITORIES_DIR_ENV, env_dir.as_posix())
    assert ResolvedSettings.from_project(project_dir).cloned_repositories_dir == env_dir

    (project_dir / "local-config.json").write_text(
        json.dumps({"cloned_repositories_dir": local_dir.as_posix()}),
        encoding="utf-8",
    )
    assert ResolvedSettings.from_project(project_dir).cloned_repositories_dir == local_dir
    assert ResolvedSettings.from_project(project_dir, cli_dir).cloned_repositories_dir == cli_dir


def test_nested_local_config_cloned_repositories_dir(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    monkeypatch.setenv(CLONED_REPOSITORIES_DIR_ENV, (tmp_path / "env").as_posix())

    (project_dir / "local-config.json").write_text(
        json.dumps({"default_configuration": {"cloned_repositories_dir": "relative-repos"}}),
        encoding="utf-8",
    )

    assert ResolvedSettings.from_project(project_dir).cloned_repositories_dir == project_dir / "relative-repos"
