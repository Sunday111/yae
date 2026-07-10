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


def test_git_status_reports_nothing_when_all_clean(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "repositories"
    root.mkdir()
    make_repo(root / "Owner" / "clean-repo")
    _write_registry(root, ["Owner/clean-repo"])

    context = _context_for(root, monkeypatch)
    GitStatusCommand().run(context, argparse.Namespace(all=False))

    assert "No repositories with changes." in capsys.readouterr().out
