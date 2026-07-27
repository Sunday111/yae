from __future__ import annotations

from pathlib import Path
import argparse
import json

from yae.commands import test as test_module
from yae.commands.base import CommandContext
from yae.commands.test import TestCommand


def _project(tmp_path: Path, build_dir: str = "build") -> Path:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "yae_project.json").write_text(
        json.dumps({"name": "TestProject", "default_configuration": {"build_dir": build_dir}}),
        encoding="utf-8",
    )
    return project_dir


def _run(monkeypatch, project_dir: Path, *, jobs: int = 4, tests_regex: str | None = None) -> list[list[str]]:
    calls: list[list[str]] = []

    def capture(command, cwd=None, env=None) -> None:  # noqa: ANN001
        calls.append(list(command))

    monkeypatch.setattr(test_module, "run_subprocess", capture)
    TestCommand().run(
        CommandContext.from_args(argparse.Namespace(project_dir=project_dir, build_dir=None)),
        argparse.Namespace(jobs=jobs, tests_regex=tests_regex),
    )
    return calls


def test_test_builds_whole_project_then_runs_ctest(tmp_path: Path, monkeypatch) -> None:
    project_dir = _project(tmp_path)
    build_dir = (project_dir / "build").as_posix()

    calls = _run(monkeypatch, project_dir, jobs=8)

    assert calls == [
        ["cmake", "--build", build_dir, "--parallel"],
        ["ctest", "--test-dir", build_dir, "--output-on-failure", "-j", "8"],
    ]


def test_test_forwards_regex_filter(tmp_path: Path, monkeypatch) -> None:
    project_dir = _project(tmp_path)
    build_dir = (project_dir / "build").as_posix()

    calls = _run(monkeypatch, project_dir, jobs=4, tests_regex=".*1464.*")

    assert calls[1] == ["ctest", "--test-dir", build_dir, "--output-on-failure", "-j", "4", "-R", ".*1464.*"]


def test_test_honors_configured_build_dir(tmp_path: Path, monkeypatch) -> None:
    project_dir = _project(tmp_path, build_dir="out/debug")
    build_dir = (project_dir / "out/debug").as_posix()

    calls = _run(monkeypatch, project_dir, jobs=2)

    assert calls[0] == ["cmake", "--build", build_dir, "--parallel"]
    assert calls[1][:3] == ["ctest", "--test-dir", build_dir]
