from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from yae.commands import format as format_module
from yae.commands.base import CommandContext
from yae.commands.format import FormatCommand
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


def _context(path: Path) -> CommandContext:
    return CommandContext.from_args(argparse.Namespace(project_dir=path))


def _run_format(monkeypatch, requested_dir: Path, format_all: bool = False) -> tuple[list[str], Path]:
    invocation: tuple[list[str], Path] | None = None

    def capture(command: list[str], cwd: Path) -> None:
        nonlocal invocation
        invocation = (command, cwd)

    monkeypatch.setattr(format_module, "run_subprocess", capture)
    FormatCommand().run(
        _context(requested_dir),
        argparse.Namespace(all=format_all, tool="test-clang-format"),
    )
    assert invocation is not None
    return invocation


def test_format_changed_files_without_yae_project(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    _make_repository(
        repository,
        {
            ".gitignore": "ignored.cpp\n",
            "changed.cpp": "int changed = 0;\n",
            "unchanged.hpp": "#pragma once\n",
            "notes.txt": "notes\n",
        },
    )
    (repository / "changed.cpp").write_text("int changed = 1;\n", encoding="utf-8")
    (repository / "staged.hpp").write_text("#pragma once\n", encoding="utf-8")
    _run_git(repository, "add", "staged.hpp")
    (repository / "new.cxx").write_text("int added = 0;\n", encoding="utf-8")
    (repository / "odd\nname.hh").write_text("#pragma once\n", encoding="utf-8")
    (repository / "ignored.cpp").write_text("int ignored = 0;\n", encoding="utf-8")

    command, cwd = _run_format(monkeypatch, repository)

    assert cwd == repository.resolve()
    assert command == [
        "test-clang-format",
        "-i",
        "--",
        "changed.cpp",
        "new.cxx",
        "odd\nname.hh",
        "staged.hpp",
    ]


def test_format_resolves_repository_root_from_nested_directory(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    _make_repository(repository, {"root.cpp": "int value = 0;\n"})
    (repository / "root.cpp").write_text("int value = 1;\n", encoding="utf-8")
    nested = repository / "some" / "nested" / "directory"
    nested.mkdir(parents=True)

    command, cwd = _run_format(monkeypatch, nested)

    assert cwd == repository.resolve()
    assert command == ["test-clang-format", "-i", "--", "root.cpp"]


def test_format_all_skips_deleted_non_source_and_ignored_files(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    _make_repository(
        repository,
        {
            ".gitignore": "ignored.cpp\n",
            "deleted.hpp": "#pragma once\n",
            "tracked.cpp": "int tracked = 0;\n",
            "tracked.txt": "not C++\n",
        },
    )
    (repository / "deleted.hpp").unlink()
    (repository / "untracked.h").write_text("#pragma once\n", encoding="utf-8")
    (repository / "ignored.cpp").write_text("int ignored = 0;\n", encoding="utf-8")

    command, cwd = _run_format(monkeypatch, repository, format_all=True)

    assert cwd == repository.resolve()
    assert command == ["test-clang-format", "-i", "--", "tracked.cpp", "untracked.h"]


def test_format_rejects_directory_outside_git_work_tree(tmp_path: Path) -> None:
    with pytest.raises(ProjectError, match="Could not find a Git work tree"):
        FormatCommand().run(
            _context(tmp_path),
            argparse.Namespace(all=False, tool="test-clang-format"),
        )


def test_format_accepts_repository_dir_and_legacy_project_dir_flags(tmp_path: Path) -> None:
    parser = argparse.ArgumentParser()
    FormatCommand().add_arguments(parser)

    repository_args = parser.parse_args(["--repository_dir", tmp_path.as_posix()])
    project_args = parser.parse_args(["--project_dir", tmp_path.as_posix()])

    assert repository_args.project_dir == tmp_path
    assert project_args.project_dir == tmp_path
