from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from yae.commands import tidy as tidy_module
from yae.commands.base import CommandContext
from yae.commands.tidy import TidyCommand
from yae.errors import ProjectError


def _run_git(repository: Path, *args: str) -> None:
    subprocess.check_call(
        ["git", "-C", repository.as_posix(), *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _make_repository(path: Path, files: dict[str, str]) -> None:
    path.mkdir(parents=True)
    subprocess.check_call(
        ["git", "init", "-b", "main", path.as_posix()],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _run_git(path, "config", "user.email", "test@example.com")
    _run_git(path, "config", "user.name", "Test User")
    for name, contents in files.items():
        destination = path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(contents, encoding="utf-8")
    _run_git(path, "add", ".")
    _run_git(path, "commit", "-m", "initial")


def _write_compilation_database(build_dir: Path) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "compile_commands.json").write_text("[]\n", encoding="utf-8")


def _context(repository: Path, build_dir: Path | None = None) -> CommandContext:
    return CommandContext.from_args(argparse.Namespace(project_dir=repository, build_dir=build_dir))


def _run_tidy(
    monkeypatch,
    repository: Path,
    *,
    build_dir: Path | None = None,
    check_all: bool = False,
    tidy_args: list[str] | None = None,
) -> tuple[list[str], Path]:
    invocation: tuple[list[str], Path] | None = None

    def capture(command: list[str], cwd: Path) -> None:
        nonlocal invocation
        invocation = (command, cwd)

    monkeypatch.setattr(tidy_module, "run_subprocess", capture)
    TidyCommand().run(
        _context(repository, build_dir),
        argparse.Namespace(all=check_all, tool="test-clang-tidy", tidy_args=tidy_args or []),
    )
    assert invocation is not None
    return invocation


def test_tidy_changed_translation_units_without_yae_project(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    _make_repository(
        repository,
        {
            "changed.cpp": "int changed = 0;\n",
            "changed.hpp": "#pragma once\n",
            "unchanged.cpp": "int unchanged = 0;\n",
        },
    )
    (repository / "changed.cpp").write_text("int changed = 1;\n", encoding="utf-8")
    (repository / "changed.hpp").write_text("#pragma once\n// changed\n", encoding="utf-8")
    (repository / "new.cu").write_text("__global__ void kernel() {}\n", encoding="utf-8")
    build_dir = tmp_path / "consumer-build"
    _write_compilation_database(build_dir)

    command, cwd = _run_tidy(
        monkeypatch,
        repository,
        build_dir=build_dir,
        tidy_args=["--", "--checks=modernize-*"],
    )

    assert cwd == repository.resolve()
    assert command == [
        "test-clang-tidy",
        f"-p={build_dir.resolve().as_posix()}",
        (repository / "changed.cpp").as_posix(),
        (repository / "new.cu").as_posix(),
        "--checks=modernize-*",
    ]


def test_tidy_all_uses_default_build_and_skips_headers(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    _make_repository(
        repository,
        {
            "include/header.hpp": "#pragma once\n",
            "source/main.cpp": "int main() { return 0; }\n",
        },
    )
    (repository / "source/extra.c").write_text("int extra(void) { return 0; }\n", encoding="utf-8")
    _write_compilation_database(repository / "build")

    command, cwd = _run_tidy(monkeypatch, repository, check_all=True)

    assert cwd == repository.resolve()
    assert command == [
        "test-clang-tidy",
        f"-p={(repository / 'build').as_posix()}",
        (repository / "source/extra.c").as_posix(),
        (repository / "source/main.cpp").as_posix(),
    ]


def test_tidy_uses_yae_project_configured_build_directory(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    project_config = {
        "name": "TestProject",
        "default_configuration": {"build_dir": "out/debug"},
    }
    _make_repository(
        repository,
        {
            "main.cpp": "int main() { return 0; }\n",
            "yae_project.json": json.dumps(project_config),
        },
    )
    build_dir = repository / "out/debug"
    _write_compilation_database(build_dir)

    command, _ = _run_tidy(monkeypatch, repository, check_all=True)

    assert command[1] == f"-p={build_dir.as_posix()}"


def test_tidy_preserves_native_compiler_argument_separator(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    _make_repository(repository, {"main.cpp": "int main() { return 0; }\n"})
    (repository / "main.cpp").write_text("int main() { return 1; }\n", encoding="utf-8")
    _write_compilation_database(repository / "build")

    command, _ = _run_tidy(
        monkeypatch,
        repository,
        tidy_args=["--", "--checks=*", "--", "-DMODE=1"],
    )

    assert command[-3:] == ["--checks=*", "--", "-DMODE=1"]


def test_tidy_requires_compilation_database(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    _make_repository(repository, {"main.cpp": "int main() { return 0; }\n"})

    with pytest.raises(ProjectError, match="Could not find a compilation database"):
        TidyCommand().run(
            _context(repository),
            argparse.Namespace(all=True, tool="test-clang-tidy", tidy_args=[]),
        )
