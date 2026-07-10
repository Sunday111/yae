from __future__ import annotations

import json
import subprocess
from pathlib import Path

from yae.cloned_repository_registry import ClonedRepositoryRegistry
from yae.global_context import GlobalContext
from yae.repository_fetcher import RepositoryFetcher


def run_git(repo: Path, *args: str) -> None:
    subprocess.check_call(["git", "-C", repo.as_posix(), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_project(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "yae_project.json").write_text(
        json.dumps({"name": "TestProject", "cpp": {"standard": "20"}}),
        encoding="utf-8",
    )


def create_checkout(path: Path, origin_url: str, branch: str = "main") -> None:
    path.mkdir(parents=True)
    subprocess.check_call(["git", "init", "-b", branch, path.as_posix()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run_git(path, "config", "user.email", "test@example.com")
    run_git(path, "config", "user.name", "Test User")
    run_git(path, "remote", "add", "origin", origin_url)
    (path / "file.txt").write_text("content\n", encoding="utf-8")
    run_git(path, "add", "file.txt")
    run_git(path, "commit", "-m", "initial")


def fetcher_for(project_dir: Path, cloned_repositories_dir: Path) -> RepositoryFetcher:
    ctx = GlobalContext(project_root=project_dir, cloned_repositories_dir=cloned_repositories_dir)
    return RepositoryFetcher(ctx, ClonedRepositoryRegistry(ctx))


def test_existing_checkout_with_matching_branch_is_registered(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    repositories_dir = tmp_path / "repositories"
    local_path = Path("Sunday111/example")
    url = "https://github.com/Sunday111/example"
    write_project(project_dir)
    create_checkout(repositories_dir / local_path, url)

    fetcher = fetcher_for(project_dir, repositories_dir)

    assert fetcher.ensure(local_path, url, "main")
    assert (repositories_dir / "registry.json").exists()


def test_existing_checkout_accepts_requested_ref_ancestor(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    repositories_dir = tmp_path / "repositories"
    local_path = Path("Sunday111/example")
    url = "https://github.com/Sunday111/example"
    write_project(project_dir)
    checkout = repositories_dir / local_path
    create_checkout(checkout, url)
    run_git(checkout, "switch", "-c", "feature")
    (checkout / "feature.txt").write_text("feature\n", encoding="utf-8")
    run_git(checkout, "add", "feature.txt")
    run_git(checkout, "commit", "-m", "feature")

    assert fetcher_for(project_dir, repositories_dir).ensure(local_path, url, "main")


def test_existing_checkout_rejects_wrong_origin(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    repositories_dir = tmp_path / "repositories"
    local_path = Path("Sunday111/example")
    write_project(project_dir)
    create_checkout(repositories_dir / local_path, "https://github.com/Sunday111/other")

    assert not fetcher_for(project_dir, repositories_dir).ensure(
        local_path,
        "https://github.com/Sunday111/example",
        "main",
    )


def test_same_repository_different_refs_can_use_different_paths(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    repositories_dir = tmp_path / "repositories"
    main_path = Path("Sunday111/example/main")
    release_path = Path("Sunday111/example/v1.0.0")
    url = "https://github.com/Sunday111/example"
    write_project(project_dir)
    create_checkout(repositories_dir / main_path, url, branch="main")
    create_checkout(repositories_dir / release_path, url, branch="v1.0.0")

    fetcher = fetcher_for(project_dir, repositories_dir)

    assert fetcher.ensure(main_path, url, "main")
    assert fetcher.ensure(release_path, url, "v1.0.0")
