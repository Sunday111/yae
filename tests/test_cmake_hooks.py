import json
import subprocess
from pathlib import Path

import pytest

from yae.cmake_project import generate_project_files
from yae.global_context import GlobalContext
from yae.module import Module
from yae.module_registry import ModuleRegistry
from yae.package import Package
from yae.resolver import ModuleOrigin
from yae.resolver import ResolvedProject


@pytest.mark.parametrize(
    ("module_type", "generate_cmake"),
    [("Library", True), ("Executable", True), ("Library", False), ("GitClone", True)],
)
def test_module_hook_runs_once_in_its_expected_scope(
    tmp_path: Path, module_type: str, generate_cmake: bool
) -> None:
    project = tmp_path / "project"
    module_dir = project / "modules" / "example"
    module_dir.mkdir(parents=True)
    repositories = tmp_path / "repositories"
    (project / "yae_project.json").write_text(
        json.dumps({"name": "hook_test", "cpp": {"standard": "23"}}), encoding="utf-8"
    )
    support_manifest = project / "yae-support.package.json"
    support_manifest.write_text("{}", encoding="utf-8")
    cmake_dir = project / "cmake"
    cmake_dir.mkdir()
    (cmake_dir / "set_compiler_options.cmake").write_text(
        "function(set_generic_compiler_options target access)\nendfunction()\n", encoding="utf-8"
    )
    manifest = module_dir / "example.module.json"
    manifest.write_text(
        json.dumps({
            "ModuleType": module_type,
            "GenerateCMakeFile": generate_cmake,
            "CompressDebugInfo": False,
            "ExtraCMakeFiles": ["hook"],
            "GitUrl": "https://github.com/example/dependency",
            "GitTag": "main",
        }),
        encoding="utf-8",
    )
    module = Module(manifest)
    generated = module_type != "GitClone" and generate_cmake
    expected_scope = module_dir if generated else project
    (module_dir / "hook.cmake").write_text(
        'add_custom_target(hook_marker)\n'
        f'if(NOT CMAKE_CURRENT_SOURCE_DIR STREQUAL "{expected_scope.as_posix()}")\n'
        '    message(FATAL_ERROR "Hook ran in the wrong scope")\n'
        'endif()\n',
        encoding="utf-8",
    )
    if module_type == "Executable":
        (module_dir / "main.cpp").write_text("int main() {}\n", encoding="utf-8")
    if not generated:
        source_dir = repositories / module.local_path if module_type == "GitClone" else module_dir
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "CMakeLists.txt").write_text("add_library(example INTERFACE)\n", encoding="utf-8")
    registry = ModuleRegistry()
    registry.add_one(module)
    resolved = ResolvedProject(
        GlobalContext(project, repositories),
        [Package(support_manifest)],
        registry,
        {module.name: ModuleOrigin.PROJECT},
    )

    generate_project_files(project, resolved_project=resolved)

    result = subprocess.run(
        [
            "cmake", "-S", str(project), "-B", str(tmp_path / "build"),
            f"-DYAE_CLONED_REPOSITORIES_DIR={repositories}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
