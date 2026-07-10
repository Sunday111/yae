from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from yae.commands.base import CommandContext
from yae.commands.common import find_cloned_project_dirs
from yae.commands.common import find_executable_module
from yae.commands.common import find_project_dir_by_run_target
from yae.errors import ProjectError
from yae.settings import CLONED_REPOSITORIES_DIR_ENV
from yae.settings import PROJECT_DIR_ENV


def context_for(project_dir: Path | None = None, cloned_repositories_dir: Path | None = None) -> CommandContext:
    return CommandContext.from_args(
        argparse.Namespace(project_dir=project_dir, cloned_repositories_dir=cloned_repositories_dir)
    )


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_project_with_local_support(project_dir: Path) -> None:
    """Builds a project that declares its own local `yae-support` package so
    resolving it never needs a network fetch."""
    write_json(
        project_dir / "yae_project.json",
        {"name": "TestProject", "cpp": {"standard": "20"}},
    )
    write_json(project_dir / "yae-support.package.json", {"modules_dir": "support_modules"})
    (project_dir / "support_modules").mkdir(parents=True, exist_ok=True)

    write_json(project_dir / "app.package.json", {"modules_dir": "src"})
    write_json(
        project_dir / "src" / "app" / "app.module.json",
        {"ModuleType": "Executable", "Dependencies": {"Public": [], "Private": ["applib"]}},
    )
    write_json(
        project_dir / "src" / "applib" / "applib.module.json",
        {"ModuleType": "Library", "Dependencies": {"Public": [], "Private": []}},
    )


def test_project_dir_uses_env_fallback(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "yae_project.json").write_text("{}", encoding="utf-8")

    unrelated_cwd = tmp_path / "somewhere-else"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)
    monkeypatch.setenv(PROJECT_DIR_ENV, project_dir.as_posix())

    assert context_for().project_dir() == project_dir.resolve()


def test_project_dir_cli_override_wins_over_env(tmp_path: Path, monkeypatch) -> None:
    env_project_dir = tmp_path / "env-project"
    env_project_dir.mkdir()
    (env_project_dir / "yae_project.json").write_text("{}", encoding="utf-8")

    cli_project_dir = tmp_path / "cli-project"
    cli_project_dir.mkdir()
    (cli_project_dir / "yae_project.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv(PROJECT_DIR_ENV, env_project_dir.as_posix())

    assert context_for(project_dir=cli_project_dir).project_dir() == cli_project_dir.resolve()


def test_project_dir_raises_when_nothing_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(PROJECT_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ProjectError):
        context_for().project_dir()


def test_find_executable_module_returns_executable(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project_with_local_support(project_dir)

    module = find_executable_module(project_dir, None, "app")

    assert module is not None
    assert module.name == "app"


def test_find_executable_module_rejects_library(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project_with_local_support(project_dir)

    assert find_executable_module(project_dir, None, "applib") is None


def test_find_executable_module_returns_none_for_unknown_name(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project_with_local_support(project_dir)

    assert find_executable_module(project_dir, None, "does-not-exist") is None


def test_cloned_repositories_dir_for_discovery_prefers_cli_override(tmp_path: Path, monkeypatch) -> None:
    cli_dir = tmp_path / "cli"
    env_dir = tmp_path / "env"
    monkeypatch.setenv(CLONED_REPOSITORIES_DIR_ENV, env_dir.as_posix())

    assert context_for(cloned_repositories_dir=cli_dir).cloned_repositories_dir_for_discovery() == cli_dir.resolve()


def test_cloned_repositories_dir_for_discovery_falls_back_to_env(tmp_path: Path, monkeypatch) -> None:
    env_dir = tmp_path / "env"
    monkeypatch.setenv(CLONED_REPOSITORIES_DIR_ENV, env_dir.as_posix())

    assert context_for().cloned_repositories_dir_for_discovery() == env_dir.resolve()


def test_cloned_repositories_dir_for_discovery_returns_none_without_source(monkeypatch) -> None:
    monkeypatch.delenv(CLONED_REPOSITORIES_DIR_ENV, raising=False)

    assert context_for().cloned_repositories_dir_for_discovery() is None


def test_find_project_dir_by_run_target_finds_cloned_project(tmp_path: Path) -> None:
    cloned_repositories_dir = tmp_path / "cloned_repositories"
    project_dir = cloned_repositories_dir / "SomeOwner" / "some-repo" / "main"
    write_project_with_local_support(project_dir)

    assert find_project_dir_by_run_target(cloned_repositories_dir, "app") == project_dir


def test_find_project_dir_by_run_target_returns_none_when_no_match(tmp_path: Path) -> None:
    cloned_repositories_dir = tmp_path / "cloned_repositories"
    project_dir = cloned_repositories_dir / "SomeOwner" / "some-repo" / "main"
    write_project_with_local_support(project_dir)

    assert find_project_dir_by_run_target(cloned_repositories_dir, "does-not-exist") is None


def test_find_project_dir_by_run_target_returns_none_for_missing_root(tmp_path: Path) -> None:
    assert find_project_dir_by_run_target(tmp_path / "does-not-exist", "app") is None


def test_find_project_dir_by_run_target_ignores_build_and_cloned_repositories_dirs(tmp_path: Path) -> None:
    cloned_repositories_dir = tmp_path / "cloned_repositories"
    project_dir = cloned_repositories_dir / "SomeOwner" / "some-repo" / "main"
    write_project_with_local_support(project_dir)

    # A decoy executable module file sitting under generated/fetched directories
    # must not count as a locally declared module.
    write_json(
        project_dir / "build" / "decoy" / "decoy.module.json",
        {"ModuleType": "Executable", "Dependencies": {"Public": [], "Private": []}},
    )
    write_json(
        project_dir / "cloned_repositories" / "decoy2" / "decoy2.module.json",
        {"ModuleType": "Executable", "Dependencies": {"Public": [], "Private": []}},
    )

    assert find_project_dir_by_run_target(cloned_repositories_dir, "decoy") is None
    assert find_project_dir_by_run_target(cloned_repositories_dir, "decoy2") is None


def test_find_project_dir_by_run_target_raises_when_ambiguous(tmp_path: Path) -> None:
    cloned_repositories_dir = tmp_path / "cloned_repositories"
    write_project_with_local_support(cloned_repositories_dir / "OwnerA" / "repo-a" / "main")
    write_project_with_local_support(cloned_repositories_dir / "OwnerB" / "repo-b" / "main")

    with pytest.raises(ProjectError):
        find_project_dir_by_run_target(cloned_repositories_dir, "app")


def test_find_cloned_project_dirs_finds_every_checkout(tmp_path: Path) -> None:
    cloned_repositories_dir = tmp_path / "cloned_repositories"
    project_a = cloned_repositories_dir / "OwnerA" / "repo-a" / "main"
    project_b = cloned_repositories_dir / "OwnerB" / "repo-b" / "v1.0"
    write_project_with_local_support(project_a)
    write_project_with_local_support(project_b)

    assert find_cloned_project_dirs(cloned_repositories_dir) == [project_a, project_b]


def test_find_cloned_project_dirs_finds_ref_qualified_checkouts(tmp_path: Path) -> None:
    cloned_repositories_dir = tmp_path / "cloned_repositories"
    project_dir = cloned_repositories_dir / "OwnerA" / "repo-a" / "main"
    write_project_with_local_support(project_dir)

    # A checkout at the shallower `owner/repo` depth is not a valid checkout in
    # the unified `{owner/repo}/{ref}` layout and must not be picked up.
    write_json(cloned_repositories_dir / "OwnerB" / "repo-b" / "yae_project.json", {"name": "Shallow"})
    # Neither is a checkout nested more deeply (e.g. a dependency fetched under
    # another checkout's own cloned-repositories directory).
    write_json(
        cloned_repositories_dir / "OwnerA" / "repo-a" / "main" / "cloned_repositories" / "OwnerC" / "repo-c" / "main" / "yae_project.json",
        {"name": "Nested"},
    )

    assert find_cloned_project_dirs(cloned_repositories_dir) == [project_dir]


def test_find_cloned_project_dirs_returns_empty_for_missing_root(tmp_path: Path) -> None:
    assert find_cloned_project_dirs(tmp_path / "does-not-exist") == []
