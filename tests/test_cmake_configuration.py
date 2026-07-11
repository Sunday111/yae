from __future__ import annotations

import json
from pathlib import Path

from yae.cmake_project.paths import CMakePathResolver
from yae.commands import common
from yae.global_context import GlobalContext


def write_project(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "yae_project.json").write_text(
        json.dumps(
            {
                "name": "TestProject",
                "default_configuration": {
                    "build_dir": "build",
                    "cmake_definitions": {"CMAKE_BUILD_TYPE": "Release"},
                },
                "cpp": {"standard": "20"},
            }
        ),
        encoding="utf-8",
    )


def test_generated_cmake_cloned_repositories_dir_default_is_project_local(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    context = GlobalContext(project_root=project_dir, cloned_repositories_dir=tmp_path / "shared")

    assert (
        CMakePathResolver(context).emit_default_cloned_repositories_dir()
        == "${CMAKE_CURRENT_SOURCE_DIR}/cloned_repositories"
    )


def test_project_local_cloned_repositories_override_uses_cmake_variable(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    cloned_repositories_dir = project_dir / "shared"
    dependency_dir = cloned_repositories_dir / "Sunday111" / "dependency"
    write_project(project_dir)
    dependency_dir.mkdir(parents=True)
    context = GlobalContext(project_root=project_dir, cloned_repositories_dir=cloned_repositories_dir)

    assert (
        CMakePathResolver(context).source_path(dependency_dir)
        == "${YAE_CLONED_REPOSITORIES_DIR}/Sunday111/dependency"
    )


def test_project_sources_under_shared_parent_can_remain_project_relative(tmp_path: Path) -> None:
    shared_root = tmp_path / "github"
    project_dir = shared_root / "Sunday111" / "project"
    source_dir = project_dir / "src" / "library"
    write_project(project_dir)
    source_dir.mkdir(parents=True)
    context = GlobalContext(project_root=project_dir, cloned_repositories_dir=shared_root)

    assert (
        CMakePathResolver(context).source_path(source_dir, prefer_project_root=True)
        == "${CMAKE_CURRENT_SOURCE_DIR}/src/library"
    )


def test_configure_passes_resolved_cloned_repositories_dir(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    shared_repos = tmp_path / "shared-repositories"
    write_project(project_dir)
    captured: dict[str, list[str]] = {}

    def capture(command: list[str], **kwargs) -> None:
        captured["command"] = command

    monkeypatch.setattr(common, "run_subprocess", capture)

    common.run_cmake_configure(
        project_dir=project_dir,
        cloned_repositories_dir=shared_repos,
        build_dir_override=None,
        extra_cmake_args=[],
    )

    assert f"-DYAE_CLONED_REPOSITORIES_DIR={shared_repos.as_posix()}" in captured["command"]
    assert "-G" in captured["command"]
    assert captured["command"][captured["command"].index("-G") + 1] == "Ninja"
    assert "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON" in captured["command"]


def test_configure_honors_generator_and_compile_commands_overrides(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["generator"] = "Unix Makefiles"
    project["default_configuration"]["cmake_definitions"]["CMAKE_EXPORT_COMPILE_COMMANDS"] = "OFF"
    project_file.write_text(json.dumps(project), encoding="utf-8")
    captured: dict[str, list[str]] = {}

    def capture(command: list[str], **kwargs) -> None:
        captured["command"] = command

    monkeypatch.setattr(common, "run_subprocess", capture)

    common.run_cmake_configure(
        project_dir=project_dir,
        cloned_repositories_dir=tmp_path / "shared-repositories",
        build_dir_override=None,
        extra_cmake_args=[],
    )

    assert "-G" in captured["command"]
    assert captured["command"][captured["command"].index("-G") + 1] == "Unix Makefiles"
    assert "-DCMAKE_EXPORT_COMPILE_COMMANDS=OFF" in captured["command"]


def test_configure_honors_cli_generator_override(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    captured: dict[str, list[str]] = {}

    def capture(command: list[str], **kwargs) -> None:
        captured["command"] = command

    monkeypatch.setattr(common, "run_subprocess", capture)

    common.run_cmake_configure(
        project_dir=project_dir,
        cloned_repositories_dir=tmp_path / "shared-repositories",
        build_dir_override=None,
        extra_cmake_args=["-G", "Unix Makefiles"],
    )

    assert captured["command"].count("-G") == 1
    assert captured["command"][captured["command"].index("-G") + 1] == "Unix Makefiles"


def test_configure_does_not_resolve_or_create_environment_directories(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["environment"] = {"SOME_CACHE_DIR": ".cache/example"}
    project_file.write_text(json.dumps(project), encoding="utf-8")
    captured: dict[str, object] = {}

    def capture(command: list[str], **kwargs) -> None:
        captured["environment"] = kwargs["env"]

    monkeypatch.setattr(common, "run_subprocess", capture)

    common.run_cmake_configure(
        project_dir=project_dir,
        cloned_repositories_dir=tmp_path / "shared-repositories",
        build_dir_override=None,
        extra_cmake_args=[],
    )

    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert environment["SOME_CACHE_DIR"] == ".cache/example"
    assert not (project_dir / ".cache" / "example").exists()
