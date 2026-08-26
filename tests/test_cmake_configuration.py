from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest

from yae.cmake_generator import CMakeGenerator
from yae.cmake_project.root_emitter import emit_root_project
from yae.cmake_project.paths import CMakePathResolver
from yae.commands import common
from yae.errors import ProjectError
from yae.global_context import GlobalContext
from yae.module import Module
from yae.module_registry import ModuleRegistry
from yae.package import Package
from yae.resolver import ModuleOrigin
from yae.resolver import ResolvedProject


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


def test_generated_cmake_cloned_repositories_dir_default_is_project_local(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    context = GlobalContext(project_root=project_dir, cloned_repositories_dir=tmp_path / "shared")

    assert (
        CMakePathResolver(context).emit_default_cloned_repositories_dir()
        == "${CMAKE_CURRENT_SOURCE_DIR}/cloned_repositories"
    )


def test_generated_root_cmake_requires_supported_cmake_version(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    context = GlobalContext(project_root=project_dir, cloned_repositories_dir=tmp_path / "shared")
    support_file = tmp_path / "yae-support" / "yae-support.package.json"
    support_file.parent.mkdir()
    support_file.write_text("{}", encoding="utf-8")
    resolved = ResolvedProject(
        context=context,
        packages=[Package(support_file)],
        module_registry=ModuleRegistry(),
        module_origins={},
    )
    output = StringIO()

    emit_root_project(CMakeGenerator(output), resolved)

    assert output.getvalue().startswith("cmake_minimum_required(VERSION 3.29)\n")


def test_generated_root_reconciles_shared_staging_ownership(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    module_file = project_dir / "src/staged/staged.module.json"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        json.dumps({"ModuleType": "Library", "CopyDirectoriesAfterBuild": ["content"]}),
        encoding="utf-8",
    )
    (module_file.parent / "content").mkdir()
    registry = ModuleRegistry()
    module = Module(module_file)
    registry.add_one(module)
    context = GlobalContext(project_root=project_dir, cloned_repositories_dir=tmp_path / "shared")
    support_file = tmp_path / "yae-support" / "yae-support.package.json"
    support_file.parent.mkdir()
    support_file.write_text("{}", encoding="utf-8")
    resolved = ResolvedProject(
        context=context,
        packages=[Package(support_file)],
        module_registry=registry,
        module_origins={module.name: ModuleOrigin.PROJECT},
    )
    output = StringIO()

    emit_root_project(CMakeGenerator(output), resolved)
    cmake = output.getvalue()

    assert "content/staged_copy_files.manifest" in cmake
    assert "add_custom_target(yae_reconcile_staging ALL" in cmake
    assert "find_package(Python3 3.12 REQUIRED COMPONENTS Interpreter)" in cmake
    assert "--reconcile" in cmake
    assert "--write-plan" in cmake
    assert 'execute_process(\n    COMMAND ${Python3_EXECUTABLE}' in cmake
    assert "manifest\\tcontent/staged_copy_files.manifest" in cmake
    assert "source\\t${CMAKE_CURRENT_SOURCE_DIR}/src/staged/content" in cmake
    assert "YAE_STAGING_PLAN_TEMP" not in cmake
    assert 'file(WRITE "${YAE_STAGING_PLAN}' not in cmake
    assert "add_dependencies(staged yae_reconcile_staging)" in cmake
    assert 'if(EXISTS "${YAE_STAGING_ROOT}")' not in cmake


def test_generated_root_conditionally_cleans_removed_last_staging_module(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    context = GlobalContext(project_root=project_dir, cloned_repositories_dir=tmp_path / "shared")
    support_file = tmp_path / "yae-support" / "yae-support.package.json"
    support_file.parent.mkdir()
    support_file.write_text("{}", encoding="utf-8")
    resolved = ResolvedProject(
        context=context,
        packages=[Package(support_file)],
        module_registry=ModuleRegistry(),
        module_origins={},
    )
    output = StringIO()

    emit_root_project(CMakeGenerator(output), resolved)
    cmake = output.getvalue()

    assert "file(GLOB_RECURSE YAE_LEGACY_STAGING_MANIFESTS" in cmake
    assert '"${CMAKE_BINARY_DIR}/yae_modules/*_copy_files_*.manifest"' in cmake
    assert 'if(EXISTS "${YAE_STAGING_ROOT}" OR YAE_LEGACY_STAGING_MANIFESTS)' in cmake
    assert "--write-plan" in cmake
    assert "add_custom_target(yae_reconcile_staging ALL" in cmake


def test_generated_root_orders_custom_module_targets_after_reconciliation(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    module_file = project_dir / "custom/custom.module.json"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        json.dumps({"ModuleType": "Library", "GenerateCMakeFile": False}),
        encoding="utf-8",
    )
    registry = ModuleRegistry()
    module = Module(module_file)
    registry.add_one(module)
    context = GlobalContext(project_root=project_dir, cloned_repositories_dir=tmp_path / "shared")
    support_file = tmp_path / "yae-support/yae-support.package.json"
    support_file.parent.mkdir()
    support_file.write_text("{}", encoding="utf-8")
    resolved = ResolvedProject(
        context=context,
        packages=[Package(support_file)],
        module_registry=registry,
        module_origins={module.name: ModuleOrigin.PROJECT},
    )
    output = StringIO()

    emit_root_project(CMakeGenerator(output), resolved)

    assert "add_dependencies(custom yae_reconcile_staging)" in output.getvalue()


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


def test_configure_uses_default_toolchain_when_none_is_configured(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    shared_repositories = tmp_path / "shared-repositories"
    write_project(project_dir)
    generated_toolchain = shared_repositories / ".yae" / "toolchains" / "default.cmake"
    captured: dict[str, object] = {}

    def generate(configuration: object, storage_dir: Path) -> Path:
        captured["configuration"] = configuration
        return generated_toolchain

    monkeypatch.setattr(common, "generate_toolchain_file", generate)
    command = capture_configure_command(project_dir, monkeypatch)

    assert captured["configuration"] == {"compiler": "gcc", "linker": "ld"}
    assert f"-DCMAKE_TOOLCHAIN_FILE={generated_toolchain.as_posix()}" in command


def test_configure_generates_toolchain_from_merged_local_configuration(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    shared_repositories = tmp_path / "shared-repositories"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["yae-toolchain"] = {
        "compiler": "clang",
        "linker": "mold",
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

    assert captured["configuration"] == {"compiler": "clang", "linker": "mold", "cpplib": "llvm-static"}
    assert captured["storage_dir"] == shared_repositories
    assert f"-DCMAKE_TOOLCHAIN_FILE={generated_toolchain.as_posix()}" in command


def test_configure_rejects_second_toolchain_file(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["yae-toolchain"] = {"compiler": "clang", "linker": "mold"}
    project_file.write_text(json.dumps(project), encoding="utf-8")

    with pytest.raises(ProjectError, match="yae-toolchain cannot be combined with CMAKE_TOOLCHAIN_FILE"):
        capture_configure_command(project_dir, monkeypatch, ["-DCMAKE_TOOLCHAIN_FILE=custom.cmake"])


def test_configure_uses_custom_cmake_toolchain_instead_of_default(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)

    def unexpected_generate(configuration: object, storage_dir: Path) -> Path:
        raise AssertionError("YAE toolchain generation should be bypassed")

    monkeypatch.setattr(common, "generate_toolchain_file", unexpected_generate)
    command = capture_configure_command(project_dir, monkeypatch, ["-DCMAKE_TOOLCHAIN_FILE=custom.cmake"])

    assert command.count("-DCMAKE_TOOLCHAIN_FILE=custom.cmake") == 1


def test_configure_rejects_toolchain_change_in_existing_build(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    write_project(project_dir)
    project_file = project_dir / "yae_project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["default_configuration"]["yae-toolchain"] = {"compiler": "clang", "linker": "mold"}
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


def test_configure_rejects_changing_to_default_toolchain_in_existing_build(tmp_path: Path, monkeypatch) -> None:
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
