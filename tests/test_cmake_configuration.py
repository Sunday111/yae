from __future__ import annotations

import json
from pathlib import Path

import pytest

from yae.cmake_project.paths import CMakePathResolver
from yae.commands import common
from yae.errors import ProjectError
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


def capture_configure_command(
    project_dir: Path,
    monkeypatch,
    extra_cmake_args: list[str] | None = None,
) -> list[str]:
    captured: dict[str, list[str]] = {}

    def capture(command: list[str], **kwargs) -> None:
        captured["command"] = command

    monkeypatch.setattr(common, "run_subprocess", capture)
    common.run_cmake_configure(
        project_dir=project_dir,
        cloned_repositories_dir=project_dir.parent / "shared-repositories",
        build_dir_override=None,
        extra_cmake_args=extra_cmake_args or [],
    )
    return captured["command"]


def test_preferred_linker_type_uses_available_linkers_in_priority_order(monkeypatch) -> None:
    available_linkers = {"ld.lld", "ld"}
    checked_linkers: list[str] = []

    def find_executable(executable: str) -> str | None:
        checked_linkers.append(executable)
        return f"/usr/bin/{executable}" if executable in available_linkers else None

    monkeypatch.setattr(common.shutil, "which", find_executable)

    assert common.find_preferred_linker_type() == "LLD"
    assert checked_linkers == ["mold", "ld.lld"]


def test_preferred_linker_type_prefers_mold(monkeypatch) -> None:
    monkeypatch.setattr(common.shutil, "which", lambda executable: f"/usr/bin/{executable}")

    assert common.find_preferred_linker_type() == "MOLD"


def test_preferred_linker_type_falls_back_to_gnu_linker(monkeypatch) -> None:
    monkeypatch.setattr(common.shutil, "which", lambda executable: "/usr/bin/ld" if executable == "ld" else None)

    assert common.find_preferred_linker_type() == "BFD"


def test_preferred_linker_type_is_unset_without_an_available_linker(monkeypatch) -> None:
    monkeypatch.setattr(common.shutil, "which", lambda executable: None)

    assert common.find_preferred_linker_type() is None


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


def test_configure_honors_linker_type_override(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["cmake_definitions"]["CMAKE_LINKER_TYPE"] = "LLD"
    project_file.write_text(json.dumps(project), encoding="utf-8")
    monkeypatch.setattr(common, "find_preferred_linker_type", lambda: "MOLD")
    command = capture_configure_command(project_dir, monkeypatch)

    assert "-DCMAKE_LINKER_TYPE=LLD" in command
    assert "-DCMAKE_LINKER_TYPE=MOLD" not in command


def test_configure_honors_project_linker(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["linker"] = "lld"
    project_file.write_text(json.dumps(project), encoding="utf-8")
    monkeypatch.setattr(common, "find_preferred_linker_type", lambda: "MOLD")
    command = capture_configure_command(project_dir, monkeypatch)

    assert "-DCMAKE_LINKER_TYPE=LLD" in command
    assert "-DCMAKE_LINKER_TYPE=MOLD" not in command


def test_configure_honors_local_linker_override(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["linker"] = "mold"
    project_file.write_text(json.dumps(project), encoding="utf-8")
    (project_dir / "local-config.json").write_text(json.dumps({"linker": "ld"}), encoding="utf-8")
    command = capture_configure_command(project_dir, monkeypatch)

    assert "-DCMAKE_LINKER_TYPE=BFD" in command
    assert "-DCMAKE_LINKER_TYPE=MOLD" not in command


def test_configure_generates_toolchain_from_merged_local_configuration(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    shared_repositories = tmp_path / "shared-repositories"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["yae-toolchain"] = {
        "compiler": "clang",
        "cpplib": "gcc-static",
    }
    project_file.write_text(json.dumps(project), encoding="utf-8")
    (project_dir / "local-config.json").write_text(
        json.dumps({"yae-toolchain": {"cpplib": "llvm-static"}}),
        encoding="utf-8",
    )
    generated_toolchain = shared_repositories / ".yae" / "toolchains" / "toolchain.cmake"
    captured: dict[str, object] = {}

    def generate(configuration: object, storage_dir: Path) -> Path:
        captured["configuration"] = configuration
        captured["storage_dir"] = storage_dir
        return generated_toolchain

    monkeypatch.setattr(common, "generate_toolchain_file", generate)
    command = capture_configure_command(project_dir, monkeypatch)

    assert captured["configuration"] == {"compiler": "clang", "cpplib": "llvm-static"}
    assert captured["storage_dir"] == shared_repositories
    assert f"-DCMAKE_TOOLCHAIN_FILE={generated_toolchain.as_posix()}" in command


def test_configure_rejects_second_toolchain_file(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["yae-toolchain"] = {"compiler": "clang"}
    project_file.write_text(json.dumps(project), encoding="utf-8")

    with pytest.raises(ProjectError, match="yae-toolchain cannot be combined with CMAKE_TOOLCHAIN_FILE"):
        capture_configure_command(project_dir, monkeypatch, ["-DCMAKE_TOOLCHAIN_FILE=custom.cmake"])


def test_configure_rejects_toolchain_change_in_existing_build(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["yae-toolchain"] = {"compiler": "clang"}
    project_file.write_text(json.dumps(project), encoding="utf-8")
    build_dir = project_dir / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text(
        "YAE_TOOLCHAIN_ID:INTERNAL=old-toolchain\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        common,
        "generate_toolchain_file",
        lambda configuration, storage_dir: storage_dir / ".yae" / "toolchains" / "new-toolchain.cmake",
    )

    with pytest.raises(ProjectError, match="yae-toolchain changed; configure a fresh build directory"):
        capture_configure_command(project_dir, monkeypatch)


def test_configure_rejects_removing_toolchain_from_existing_build(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    build_dir = project_dir / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text(
        "YAE_TOOLCHAIN_ID:INTERNAL=configured-toolchain\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectError, match="yae-toolchain changed; configure a fresh build directory"):
        capture_configure_command(project_dir, monkeypatch)


def test_configure_rejects_unknown_linker(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["linker"] = "gold"
    project_file.write_text(json.dumps(project), encoding="utf-8")

    with pytest.raises(ProjectError, match="Unknown linker 'gold'. Expected one of: mold, lld, ld"):
        common.run_cmake_configure(
            project_dir=project_dir,
            cloned_repositories_dir=tmp_path / "shared-repositories",
            build_dir_override=None,
            extra_cmake_args=[],
        )


def test_configure_honors_cli_linker_type_override(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    monkeypatch.setattr(common, "find_preferred_linker_type", lambda: "MOLD")
    command = capture_configure_command(project_dir, monkeypatch, ["-DCMAKE_LINKER_TYPE=LLD"])

    assert command.count("-DCMAKE_LINKER_TYPE=LLD") == 1
    assert "-DCMAKE_LINKER_TYPE=MOLD" not in command


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
