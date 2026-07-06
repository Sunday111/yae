from __future__ import annotations

from pathlib import Path

from yae.cmake_generator import CMakeGenerator
from yae.cmake_project.module_emitter import emit_module_cmake_file
from yae.cmake_project.root_emitter import emit_root_project
from yae.module import ModuleType
from yae.resolver import resolve_project


def generate_project_files(project_dir: Path, external_modules_dir: Path | None = None) -> None:
    resolved_project = resolve_project(project_dir, external_modules_dir)
    ctx = resolved_project.context
    module_registry = resolved_project.module_registry

    with open(CMakeGenerator.make_file_path(ctx.root_dir), mode="w", encoding="utf-8") as file:
        emit_root_project(CMakeGenerator(file), resolved_project)

    for module in (module_registry.find(module_name) for module_name in module_registry.topological_sort()):
        if module is None:
            continue
        if module.module_type == ModuleType.GITCLONE:
            continue
        if not module.generate_cmake_file:
            continue
        emit_module_cmake_file(module, module_registry)
