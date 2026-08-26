from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from yae import git
from yae.commands.base import CommandContext
from yae.commands.git_status import GitStatusCommand
from yae.settings import CLONED_REPOSITORIES_DIR_ENV
from yae.settings import PROJECT_DIR_ENV


def _run_git(repo: Path, *args: str) -> None:
    subprocess.check_call(["git", "-C", repo.as_posix(), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.check_call(["git", "init", "-b", "main", path.as_posix()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _run_git(path, "config", "user.email", "test@example.com")
    _run_git(path, "config", "user.name", "Test User")
    (path / "file.txt").write_text("content\n", encoding="utf-8")
    _run_git(path, "add", "file.txt")
    _run_git(path, "commit", "-m", "initial")


def test_status_short_reports_dirty_clean_and_non_repo(tmp_path: Path) -> None:
    clean = tmp_path / "clean"
    dirty = tmp_path / "dirty"
    make_repo(clean)
    make_repo(dirty)
    (dirty / "untracked.txt").write_text("x\n", encoding="utf-8")

    assert git.status_short(clean) == []
    assert git.status_short(dirty) == ["?? untracked.txt"]
    assert git.status_short(tmp_path / "not-a-repo") is None


def _context_for(cloned_repositories_dir: Path, monkeypatch) -> CommandContext:
    monkeypatch.delenv(PROJECT_DIR_ENV, raising=False)
    monkeypatch.delenv(CLONED_REPOSITORIES_DIR_ENV, raising=False)
    monkeypatch.chdir(cloned_repositories_dir)  # a directory without a yae_project.json
    return CommandContext.from_args(
        argparse.Namespace(project_dir=None, cloned_repositories_dir=cloned_repositories_dir)
    )


def _write_registry(cloned_repositories_dir: Path, local_paths: list[str]) -> None:
    registry = {lp: {"GitUrl": f"https://github.com/{lp}", "GitTag": "main"} for lp in local_paths}
    (cloned_repositories_dir / "registry.json").write_text(json.dumps(registry), encoding="utf-8")


def test_git_status_shows_only_changed_by_default(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    root.mkdir()
    make_repo(root / "Owner" / "clean-repo")
    make_repo(root / "Owner" / "dirty-repo")
    (root / "Owner" / "dirty-repo" / "new.txt").write_text("x\n", encoding="utf-8")
    _write_registry(root, ["Owner/clean-repo", "Owner/dirty-repo"])

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    out = capsys.readouterr().out
    assert "Owner/dirty-repo" in out
    assert "new.txt" in out
    assert "Owner/clean-repo" not in out


def test_git_status_all_lists_clean_repositories(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    root.mkdir()
    make_repo(root / "Owner" / "clean-repo")
    _write_registry(root, ["Owner/clean-repo"])

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=True))

    out = capsys.readouterr().out
    assert "Owner/clean-repo" in out
    assert "clean" in out


def test_git_status_discovers_unregistered_versioned_checkout(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    root.mkdir()
    repo = root / "Owner" / "project" / "main"
    make_repo(repo)
    (repo / "new.txt").write_text("x\n", encoding="utf-8")

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    out = capsys.readouterr().out
    assert "Owner/project/main" in out
    assert "new.txt" in out


def test_git_status_discovery_does_not_follow_symlinks_outside_root(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    root.mkdir()
    owner_target = tmp_path / "outside-owner"
    repository_target = tmp_path / "outside-repository"
    checkout_target = tmp_path / "outside-checkout"
    make_repo(owner_target / "project" / "main")
    make_repo(repository_target / "main")
    make_repo(checkout_target)
    (owner_target / "project" / "main" / "owner.txt").write_text("x\n", encoding="utf-8")
    (repository_target / "main" / "repository.txt").write_text("x\n", encoding="utf-8")
    (checkout_target / "checkout.txt").write_text("x\n", encoding="utf-8")
    (root / "linked-owner").symlink_to(owner_target, target_is_directory=True)
    (root / "Owner").mkdir()
    (root / "Owner" / "linked-repository").symlink_to(repository_target, target_is_directory=True)
    (root / "Owner" / "project").mkdir()
    (root / "Owner" / "project" / "linked-checkout").symlink_to(checkout_target, target_is_directory=True)

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    assert "No repositories with changes." in capsys.readouterr().out


def test_git_status_ignores_registry_paths_outside_root(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    root.mkdir()
    outside = tmp_path / "outside"
    make_repo(outside)
    (outside / "new.txt").write_text("x\n", encoding="utf-8")
    _write_registry(root, ["../outside"])

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    assert "No repositories with changes." in capsys.readouterr().out


def test_git_status_labels_checkouts_relative_to_symlinked_root(tmp_path, monkeypatch, capsys) -> None:
    real_root = tmp_path / "real-repositories"
    real_root.mkdir()
    repo = real_root / "Owner" / "project" / "main"
    make_repo(repo)
    (repo / "new.txt").write_text("x\n", encoding="utf-8")
    linked_root = tmp_path / "repositories"
    linked_root.symlink_to(real_root, target_is_directory=True)

    context = _context_for(linked_root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    out = capsys.readouterr().out
    assert "Owner/project/main" in out
    assert real_root.as_posix() not in out


def test_git_status_reports_nothing_when_all_clean(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    root.mkdir()
    make_repo(root / "Owner" / "clean-repo")
    _write_registry(root, ["Owner/clean-repo"])

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    assert "No repositories with changes." in capsys.readouterr().out


def make_clone_with_unpushed_commits(origin: Path, clone: Path, commit_count: int) -> None:
    subprocess.check_call(
        ["git", "clone", origin.as_posix(), clone.as_posix()],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _run_git(clone, "config", "user.email", "test@example.com")
    _run_git(clone, "config", "user.name", "Test User")
    for index in range(commit_count):
        (clone / f"local{index}.txt").write_text("x\n", encoding="utf-8")
        _run_git(clone, "add", f"local{index}.txt")
        _run_git(clone, "commit", "-m", f"local {index}")


def test_unpushed_commit_count(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    clone = tmp_path / "clone"
    make_repo(origin)
    make_clone_with_unpushed_commits(origin, clone, commit_count=2)

    assert git.unpushed_commit_count(clone) == 2
    assert git.unpushed_commit_count(origin) is None  # no upstream configured


def test_git_status_reports_unpushed_commits_in_clean_repo(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    origin = tmp_path / "origin"
    root.mkdir()
    make_repo(origin)
    make_clone_with_unpushed_commits(origin, root / "Owner" / "ahead-repo", commit_count=2)
    _write_registry(root, ["Owner/ahead-repo"])

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    out = capsys.readouterr().out
    assert "Owner/ahead-repo" in out
    assert "2 commits not pushed" in out


def test_git_status_reports_branch_without_upstream(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    origin = tmp_path / "origin"
    root.mkdir()
    make_repo(origin)
    repo = root / "Owner" / "local-branch-repo"
    make_clone_with_unpushed_commits(origin, repo, commit_count=0)
    _run_git(repo, "switch", "-c", "feature")

    _write_registry(root, ["Owner/local-branch-repo"])

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    out = capsys.readouterr().out
    assert "Owner/local-branch-repo" in out
    assert "branch has no upstream" in out


def test_git_status_silent_about_detached_head_and_no_remotes(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    origin = tmp_path / "origin"
    root.mkdir()
    make_repo(origin)

    # Dependency checkouts are typically detached at a tag.
    detached = root / "Owner" / "detached-repo"
    make_clone_with_unpushed_commits(origin, detached, commit_count=0)
    _run_git(detached, "checkout", "--detach", "HEAD")

    # A repository without remotes has nowhere to push to.
    make_repo(root / "Owner" / "no-remote-repo")

    _write_registry(root, ["Owner/detached-repo", "Owner/no-remote-repo"])

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    assert "No repositories with changes." in capsys.readouterr().out
