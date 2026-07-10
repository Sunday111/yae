from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from yae.commands.clone import clone_github_project
from yae.errors import ProjectError


def test_clone_github_project_uses_ref_qualified_repository_path(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_check_call(command: list[str], **kwargs) -> None:
        calls.append(command)

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)

    destination = clone_github_project(
        "https://github.com/Sunday111/verlet_cuda",
        "main",
        tmp_path,
        show_clone_progress=False,
    )

    # A direct clone lands at the same {owner/repo}/{ref} path the resolver checks
    # dependencies out to, so a direct clone and a dependency checkout dedupe.
    assert destination == tmp_path / "Sunday111" / "verlet_cuda" / "main"
    assert calls == [
        [
            "git",
            "clone",
            "--branch",
            "main",
            "https://github.com/Sunday111/verlet_cuda",
            (tmp_path / "Sunday111" / "verlet_cuda" / "main").as_posix(),
        ]
    ]


def test_clone_github_project_can_show_git_progress(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_check_call(command: list[str], **kwargs) -> None:
        calls.append(command)

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)

    clone_github_project(
        "https://github.com/Sunday111/verlet_cuda",
        "develop",
        tmp_path,
        show_clone_progress=True,
    )

    assert calls[0][:4] == ["git", "clone", "--progress", "--branch"]


def test_clone_github_project_rejects_non_github_url(tmp_path: Path) -> None:
    with pytest.raises(ProjectError):
        clone_github_project(
            "https://example.com/Sunday111/verlet_cuda",
            "main",
            tmp_path,
            show_clone_progress=False,
        )
