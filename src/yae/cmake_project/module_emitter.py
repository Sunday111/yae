from __future__ import annotations

from pathlib import Path
from typing import Iterable

from yae import yae_constants
from yae.cmake_generator import CMakeGenerator
from yae.cmake_project.staging import copy_directories_by_destination
from yae.cmake_project.staging import copy_target_name
from yae.cmake_project.staging import staging_manifest_relative_path
from yae.errors import ModuleGraphError
from yae.module import CPP_SUFFIXES
from yae.module import CUDA_SUFFIXES
from yae.module import Module
from yae.module import ModuleType
from yae.module_registry import ModuleRegistry


def emit_copy_target(gen: CMakeGenerator, module: Module) -> None:
    """Emits the step that stages this module's directories next to the built binary.

    Per module, so that building a target stages the content of that target and what it
    links, and nothing else - a module outside the build leaves the output directory
    alone. The manifest is what lets the module remove its own stale files without
    touching the ones another module staged into the same place.
    """

    copy_dirs_by_destination = copy_directories_by_destination(module)
    if not copy_dirs_by_destination:
        return

    target = copy_target_name(module)
    gen.line(f"add_custom_target({target} ALL")
    for destination, copy_dirs in copy_dirs_by_destination.items():
        gen.line('    COMMAND ${Python3_EXECUTABLE} "${YAE_SUPPORT_ROOT}/scripts/stage_directories.py"')
        gen.line(f'            --destination "${{CMAKE_RUNTIME_OUTPUT_DIRECTORY}}/{destination}"')
        gen.line('            --destination-root "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"')
        for copy_dir in copy_dirs:
            relative_dir = copy_dir.relative_to(module.root_dir).as_posix()
            gen.line(f'            --source "${{CMAKE_CURRENT_SOURCE_DIR}}/{relative_dir}"')
        manifest_path = staging_manifest_relative_path(module, destination).as_posix()
        gen.line(f'            --manifest "${{YAE_STAGING_ROOT}}/{manifest_path}"')
        gen.line('            --active-manifests "${YAE_STAGING_PLAN}"')
    gen.line(f'    COMMENT "stage content of {module.cmake_target_name}"')
    gen.line("    VERBATIM)")
    gen.line(f"add_dependencies({target} yae_reconcile_staging)")
    gen.line(f"add_dependencies({module.cmake_target_name} {target})")


def emit_module_cmake_file(module: Module, module_registry: ModuleRegistry) -> None:
    cmake_file_path = CMakeGenerator.make_file_path(module.root_dir)
    with open(cmake_file_path, mode="w", encoding="utf-8") as file:
        gen = CMakeGenerator(file)
        gen.version_line(*yae_constants.CMAKE_MINIMUM_VERSION)

        rel_sources = sorted(path.relative_to(module.root_dir) for path in module.source_files)
        has_cpp_files = any(path.suffix in CPP_SUFFIXES for path in rel_sources)
        has_cuda_files = any(path.suffix in CUDA_SUFFIXES for path in rel_sources)
        is_interface_library = False

        if has_cuda_files:
            gen.line("enable_language(CUDA)")

        gen.include("set_compiler_options")
        if module.specifies_lto:
            gen.include("yae_lto")
        if module.module_type == ModuleType.EXECUTABLE and module.compress_debug_info:
            gen.include("yae_debug_info_compression")

        src_var_name = "module_source_files"
        gen.make_paths_list_variable(src_var_name, rel_sources)

        if module.module_type == ModuleType.LIBRARY:
            lib_type = "STATIC"
            if not has_cpp_files:
                lib_type = "INTERFACE"
                is_interface_library = True
            gen.add_library(module.name, lib_type, src_var_name)
        elif module.module_type == ModuleType.EXECUTABLE:
            if not has_cpp_files:
                raise ModuleGraphError(f"Executable module '{module.name}' has no .cpp source files")
            gen.add_executable(module.name, src_var_name)
        else:
            raise ModuleGraphError(f"Unhandled module type: {module.module_type}")

        public_access = "PUBLIC"
        private_access = "PRIVATE"
        if is_interface_library:
            public_access = "INTERFACE"
            private_access = public_access

        gen.line(f"set_generic_compiler_options({module.name} {private_access})")
        gen.target_link_libraries(module.name, public_access, _to_cmake_modules(module.public_dependencies, module_registry))
        gen.target_link_libraries(module.name, private_access, _to_cmake_modules(module.private_dependencies, module_registry))
        gen.target_include_directories(module.name, public_access, [Path("code/public")])
        gen.target_include_directories(module.name, private_access, [Path("code/private")])

        if module.module_type == ModuleType.EXECUTABLE and module.compress_debug_info:
            gen.line(f"enable_debug_info_compression_for({module.name})")
        for extra_cmake in module.extra_cmake_files:
            gen.include(f"${{CMAKE_CURRENT_SOURCE_DIR}}/{extra_cmake}.cmake")

        if module.specifies_lto:
            if module.enable_lto:
                gen.line(f"enable_lto_for({module.name})")
            else:
                gen.line(f"disable_lto_for({module.name})")

        if module.enable_testing:
            gen.line("enable_testing()")
            gen.include("GoogleTest")
            gen.line(f"gtest_discover_tests({module.name})")

        emit_copy_target(gen, module)



def _to_cmake_modules(modules: Iterable[str], module_registry: ModuleRegistry) -> list[str]:
    result = []
    for name in modules:
        module = module_registry.find(name)
        if module is None:
            raise RuntimeError(f"Unknown module dependency {name}")
        if module.cmake_modular_targets:
            result.extend(module.cmake_modular_targets)
        else:
            result.append(module.cmake_target_name)
    return result
