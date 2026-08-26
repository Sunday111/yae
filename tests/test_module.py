import json
from pathlib import Path

import pytest

from yae.cmake_project.module_emitter import emit_module_cmake_file
from yae.errors import ModuleGraphError
from yae.module import Module
from yae.module_registry import ModuleRegistry


def write_module(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_github_gitclone_local_path_includes_ref(tmp_path: Path) -> None:
    module_file = tmp_path / "dependency.module.json"
    write_module(
        module_file,
        {
            "ModuleType": "GitClone",
            "GitUrl": "https://github.com/Sunday111/klgl",
            "GitTag": "feature/rendering",
            "LocalPath": "legacy/path",
        },
    )

    assert Module(module_file).local_path == Path("Sunday111/klgl/feature_rendering")


def test_non_github_gitclone_local_path_uses_declared_path(tmp_path: Path) -> None:
    module_file = tmp_path / "dependency.module.json"
    write_module(
        module_file,
        {
            "ModuleType": "GitClone",
            "GitUrl": "https://example.com/vendor/repo",
            "GitTag": "main",
            "LocalPath": "vendor/repo",
        },
    )

    assert Module(module_file).local_path == Path("vendor/repo")


@pytest.mark.parametrize("local_path", ["../outside", "/outside", ""])
def test_non_github_gitclone_local_path_stays_in_repositories_root(tmp_path: Path, local_path: str) -> None:
    module_file = tmp_path / "dependency.module.json"
    write_module(
        module_file,
        {
            "ModuleType": "GitClone",
            "GitUrl": "ssh://git.example.com/dependency",
            "GitTag": "v1",
            "LocalPath": local_path,
        },
    )

    with pytest.raises(ModuleGraphError, match="must stay within the repositories root"):
        Module(module_file)


def test_debug_info_compression_is_enabled_by_default(tmp_path: Path) -> None:
    module_file = tmp_path / "app.module.json"
    write_module(module_file, {"ModuleType": "Executable"})

    assert Module(module_file).compress_debug_info


def test_debug_info_compression_can_be_disabled(tmp_path: Path) -> None:
    module_file = tmp_path / "app.module.json"
    write_module(module_file, {"ModuleType": "Executable", "CompressDebugInfo": False})

    assert not Module(module_file).compress_debug_info


def test_cmake_options_require_boolean_values(tmp_path: Path) -> None:
    module_file = tmp_path / "dependency.module.json"
    write_module(module_file, {"ModuleType": "Library", "CMakeOptions": {"BUILD_TESTING": "OFF"}})

    with pytest.raises(ModuleGraphError, match="CMake option 'BUILD_TESTING' must be boolean"):
        Module(module_file)


def emit_cmake(
    tmp_path: Path,
    module_type: str,
    compress_debug_info: bool | None = None,
) -> str:
    module_file = tmp_path / "target.module.json"
    module_data: dict[str, object] = {"ModuleType": module_type}
    if compress_debug_info is not None:
        module_data["CompressDebugInfo"] = compress_debug_info
    write_module(module_file, module_data)
    source_dir = tmp_path / "code" / "private"
    source_dir.mkdir(parents=True)
    (source_dir / "source.cpp").write_text("int main() {}", encoding="utf-8")

    module = Module(module_file)
    emit_module_cmake_file(module, ModuleRegistry())
    return (tmp_path / "CMakeLists.txt").read_text(encoding="utf-8")


def test_executable_cmake_enables_debug_info_compression_by_default(tmp_path: Path) -> None:
    cmake = emit_cmake(tmp_path, "Executable")

    assert cmake.startswith("cmake_minimum_required(VERSION 3.29)\n")
    assert "include(yae_debug_info_compression)" in cmake
    assert "enable_debug_info_compression_for(target)" in cmake


def test_executable_cmake_can_disable_debug_info_compression(tmp_path: Path) -> None:
    cmake = emit_cmake(tmp_path, "Executable", False)

    assert "yae_debug_info_compression" not in cmake


def test_library_cmake_does_not_enable_debug_info_compression(tmp_path: Path) -> None:
    cmake = emit_cmake(tmp_path, "Library")

    assert "yae_debug_info_compression" not in cmake


def test_module_staging_groups_sources_and_uses_shared_ownership_state(tmp_path: Path) -> None:
    module_file = tmp_path / "target.module.json"
    write_module(
        module_file,
        {
            "ModuleType": "Library",
            "CopyDirectoriesAfterBuild": ["first/content", "second/content"],
        },
    )
    source_dir = tmp_path / "code" / "private"
    source_dir.mkdir(parents=True)
    (source_dir / "source.cpp").write_text("void f() {}", encoding="utf-8")
    (tmp_path / "first/content").mkdir(parents=True)
    (tmp_path / "second/content").mkdir(parents=True)

    emit_module_cmake_file(Module(module_file), ModuleRegistry())
    cmake = (tmp_path / "CMakeLists.txt").read_text(encoding="utf-8")

    assert cmake.count("scripts/stage_directories.py") == 1
    assert '--source "${CMAKE_CURRENT_SOURCE_DIR}/first/content"' in cmake
    assert '--source "${CMAKE_CURRENT_SOURCE_DIR}/second/content"' in cmake
    assert '--manifest "${YAE_STAGING_ROOT}/content/target_copy_files.manifest"' in cmake
    assert '--active-manifests "${YAE_STAGING_PLAN}"' in cmake
    assert '--destination-root "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"' in cmake
    assert "add_dependencies(target_copy_files yae_reconcile_staging)" in cmake
