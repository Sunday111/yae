from __future__ import annotations

from yae import yae_constants
from yae.cmake_generator import CMakeGenerator
from yae.cmake_project.paths import CMakePathResolver
from yae.module import ModuleType
from yae.resolver import ModuleOrigin
from yae.resolver import ResolvedProject


def emit_root_project(gen: CMakeGenerator, resolved_project: ResolvedProject) -> None:
    ctx = resolved_project.context
    module_registry = resolved_project.module_registry
    path_resolver = CMakePathResolver(ctx)

    gen.version_line(3, 20)
    gen.line()
    gen.project_line(ctx.project_config.name)
    gen.line()
    gen.define_cpp_standard(ctx.project_config.cpp_standard)
    gen.require_cpp_standard()
    gen.disable_cpp_extensions()

    _emit_output_directories(gen)

    gen.line()
    gen.line("# Set path to cloned repositories sources")
    gen.line(
        f'set({path_resolver.cloned_repositories_var_name} "{path_resolver.emit_default_cloned_repositories_dir()}" '
        'CACHE PATH "Path to YAE cloned repository checkouts")'
    )

    gen.line()
    gen.line(
        f'set({path_resolver.support_root_var_name} "{path_resolver.source_path(resolved_project.support_package.root_dir)}")'
    )
    gen.line(f'set({path_resolver.project_root_var_name} "${{CMAKE_CURRENT_SOURCE_DIR}}")')
    gen.line(
        f'set(CMAKE_MODULE_PATH "${{CMAKE_MODULE_PATH}};${{{path_resolver.support_root_var_name}}}/cmake")'
    )
    gen.line()
    gen.line()

    if ctx.project_config.enable_lto_globally is not None:
        gen.include("yae_lto")
        gen.line("enable_lto_globally()" if ctx.project_config.enable_lto_globally else "disable_lto_globally()")

    _emit_staging_interpreter(gen, resolved_project)

    gen.line()
    gen.line()

    added_subdirs: set[str] = set()
    for module_name in module_registry.topological_sort():
        module = module_registry.find(module_name)
        if module is None:
            continue

        prefer_project_root = resolved_project.module_origins[module.name] == ModuleOrigin.PROJECT
        module_source_path = path_resolver.module_source_path(module, prefer_project_root=prefer_project_root)
        if module_source_path.cmake_path in added_subdirs:
            continue

        variable_with_path_to_module = f"YAE_{module.name}_SOURCES"
        if module.module_type == ModuleType.GITCLONE:
            gen.line(f"# {module.git_url} {module.git_tag}")
        gen.line(f"set({variable_with_path_to_module} {module_source_path.cmake_path})")

        if module.should_add_subdirectory:
            for variable_name, variable_value in module.cmake_options.items():
                if not gen.option(variable_name, variable_value):
                    return

            local_cmake_file_path = f"/{module.cmake_file_path}" if module.cmake_file_path else ""
            gen.add_subdirectory(
                f"${{{variable_with_path_to_module}}}{local_cmake_file_path}",
                is_system=True,
                exclude_from_all=module.cmake_exclude_from_all,
                build_directory=f"{yae_constants.GENERATED_MODULES_SUBDIR}/{module_source_path.local_path.as_posix()}",
            )
            gen.line()
            added_subdirs.add(module_source_path.cmake_path)

        for extra_cmake in module.extra_cmake_files:
            module_root = path_resolver.source_path(module.root_dir, prefer_project_root=prefer_project_root)
            gen.include(f"{module_root}/{extra_cmake}.cmake")

    gen.line()
    gen.line("enable_testing()")


def _emit_staging_interpreter(gen: CMakeGenerator, resolved_project: ResolvedProject) -> None:
    """Finds the interpreter that modules staging content will use.

    Found here rather than baked in as the one yae happens to be running under: the
    generated project has to build without yae. Modules are added below this, so they
    all see Python3_EXECUTABLE.
    """

    module_registry = resolved_project.module_registry
    stages_anything = any(
        (module := module_registry.find(module_name)) is not None and any(module.post_build_copy_dirs)
        for module_name in module_registry.topological_sort()
    )
    if not stages_anything:
        return

    gen.line()
    gen.line("find_package(Python3 REQUIRED COMPONENTS Interpreter)")


def _emit_output_directories(gen: CMakeGenerator) -> None:
    gen.line("# Set output directories for binaries")
    gen.line(f"set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${{CMAKE_CURRENT_BINARY_DIR}}/{yae_constants.RUNTIME_OUTPUT_SUBDIR})")
    gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})")
    gen.line("# Set output directories for archives")
    gen.line(f"set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${{CMAKE_CURRENT_BINARY_DIR}}/{yae_constants.ARCHIVE_OUTPUT_SUBDIR})")
    gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})")
    gen.line("# Set output directories for libraries")
    gen.line(f"set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${{CMAKE_CURRENT_BINARY_DIR}}/{yae_constants.ARCHIVE_OUTPUT_SUBDIR})")
    gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})")
    gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_DEBUG ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})")
