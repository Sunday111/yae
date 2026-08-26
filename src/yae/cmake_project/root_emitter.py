from __future__ import annotations

from yae import yae_constants
from yae.cmake_generator import CMakeGenerator
from yae.cmake_project.paths import CMakePathResolver
from yae.cmake_project.staging import copy_directories_by_destination
from yae.cmake_project.staging import staging_manifest_relative_path
from yae.module import CUDA_SUFFIXES
from yae.module import Module
from yae.module import ModuleType
from yae.module_registry import ModuleRegistry
from yae.resolver import ModuleOrigin
from yae.resolver import ResolvedProject
from yae.system_triple import current_system_triple


def emit_root_project(gen: CMakeGenerator, resolved_project: ResolvedProject) -> None:
    ctx = resolved_project.context
    module_registry = resolved_project.module_registry
    path_resolver = CMakePathResolver(ctx)

    gen.version_line(*yae_constants.CMAKE_MINIMUM_VERSION)
    gen.line()
    gen.project_line(ctx.project_config.name)
    gen.line()
    gen.define_cpp_standard(ctx.project_config.cpp_standard)
    gen.require_cpp_standard()
    gen.disable_cpp_extensions()
    if _project_has_cuda(module_registry):
        gen.define_cuda_standard(ctx.project_config.cpp_standard)
        gen.require_cuda_standard()
        gen.disable_cuda_extensions()

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

    _emit_staging_reconciliation(gen, resolved_project)

    gen.line()
    gen.line()

    added_subdirs: set[str] = set()
    for module_name in module_registry.topological_sort():
        module = module_registry.find(module_name)
        if module is None:
            continue

        # A binary dependency is already unpacked in the shared root; expose its
        # own CMake package here, before any consumer's add_subdirectory, so the
        # imported target is visible to link against. No sources, so nothing else
        # in the loop applies.
        if module.module_type == ModuleType.BINARY:
            _emit_binary_dependency(gen, module, path_resolver)
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
                gen.option(variable_name, variable_value)

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

    _emit_staging_target_dependencies(gen, module_registry)

    gen.line()
    gen.line("enable_testing()")


def _emit_binary_dependency(gen: CMakeGenerator, module: Module, path_resolver: CMakePathResolver) -> None:
    triple = current_system_triple()
    extract_dir = module.binary_extract_dir(triple)
    cmake_path = path_resolver.source_path(extract_dir)
    gen.line(f"# binary dependency {module.name} ({triple})")
    # NO_DEFAULT_PATH pins resolution to the unpacked SDK - never a same-named
    # package elsewhere on the system - and REQUIRED fails loudly if the fetch
    # step did not produce it.
    gen.line(
        f"find_package({module.find_package_name} CONFIG REQUIRED "
        f"PATHS {cmake_path} NO_DEFAULT_PATH)"
    )
    gen.line()


def _project_has_cuda(module_registry: ModuleRegistry) -> bool:
    return any(
        (module := module_registry.find(module_name)) is not None
        and any(path.suffix in CUDA_SUFFIXES for path in module.source_files)
        for module_name in module_registry.topological_sort()
    )


def _emit_staging_reconciliation(gen: CMakeGenerator, resolved_project: ResolvedProject) -> None:
    module_registry = resolved_project.module_registry
    path_resolver = CMakePathResolver(resolved_project.context)
    active_owners: list[tuple[str, list[str]]] = []
    for module_name in module_registry.topological_sort():
        module = module_registry.find(module_name)
        if module is None or module.module_type in (ModuleType.GITCLONE, ModuleType.BINARY):
            continue
        if not module.generate_cmake_file:
            continue
        prefer_project_root = resolved_project.module_origins[module.name] == ModuleOrigin.PROJECT
        module_source_path = path_resolver.source_path(
            module.root_dir, prefer_project_root=prefer_project_root
        )
        for destination, copy_dirs in copy_directories_by_destination(module).items():
            sources = [
                f"{module_source_path}/{copy_dir.relative_to(module.root_dir).as_posix()}"
                for copy_dir in copy_dirs
            ]
            active_owners.append(
                (staging_manifest_relative_path(module, destination).as_posix(), sources)
            )

    active_owners.sort()
    gen.line('set(YAE_STAGING_ROOT "${CMAKE_BINARY_DIR}/.yae-staging")')
    gen.line('set(YAE_STAGING_PLAN "${YAE_STAGING_ROOT}/active-manifests.txt")')
    conditional = not active_owners
    indentation = ""
    if conditional:
        gen.line("file(GLOB_RECURSE YAE_LEGACY_STAGING_MANIFESTS")
        gen.line("    LIST_DIRECTORIES FALSE")
        gen.line('    "${CMAKE_BINARY_DIR}/yae_modules/*_copy_files_*.manifest")')
        gen.line('if(EXISTS "${YAE_STAGING_ROOT}" OR YAE_LEGACY_STAGING_MANIFESTS)')
        indentation = "    "

    gen.line(f"{indentation}find_package(Python3 3.12 REQUIRED COMPONENTS Interpreter)")
    gen.line(f"{indentation}execute_process(")
    gen.line(f"{indentation}    COMMAND ${{Python3_EXECUTABLE}}")
    gen.line(f'{indentation}            "${{YAE_SUPPORT_ROOT}}/scripts/stage_directories.py"')
    gen.line(f"{indentation}            --write-plan")
    gen.line(f'{indentation}            --manifest-root "${{YAE_STAGING_ROOT}}"')
    gen.line(f'{indentation}            --active-manifests "${{YAE_STAGING_PLAN}}"')
    for manifest, sources in active_owners:
        gen.line(
            f'{indentation}            --plan-entry "manifest\\t{manifest}"'
        )
        for source in sources:
            gen.line(
                f'{indentation}            --plan-entry "source\\t{source}"'
            )
    gen.line(f"{indentation}    RESULT_VARIABLE YAE_STAGING_PLAN_RESULT")
    gen.line(f"{indentation}    ERROR_VARIABLE YAE_STAGING_PLAN_ERROR)")
    gen.line(f'{indentation}if(NOT YAE_STAGING_PLAN_RESULT EQUAL 0)')
    gen.line(
        f'{indentation}    message(FATAL_ERROR "Failed to publish staging plan: '
        '${YAE_STAGING_PLAN_ERROR}")'
    )
    gen.line(f"{indentation}endif()")
    gen.line(f"{indentation}add_custom_target(yae_reconcile_staging ALL")
    gen.line(
        f'{indentation}    COMMAND ${{Python3_EXECUTABLE}} '
        '"${YAE_SUPPORT_ROOT}/scripts/stage_directories.py"'
    )
    gen.line(f'{indentation}            --reconcile')
    gen.line(f'{indentation}            --destination-root "${{CMAKE_RUNTIME_OUTPUT_DIRECTORY}}"')
    gen.line(f'{indentation}            --manifest-root "${{YAE_STAGING_ROOT}}"')
    gen.line(f'{indentation}            --active-manifests "${{YAE_STAGING_PLAN}}"')
    gen.line(f'{indentation}            --legacy-manifest-root "${{CMAKE_BINARY_DIR}}/yae_modules"')
    gen.line(f'{indentation}    COMMENT "reconcile staged content"')
    gen.line(f"{indentation}    VERBATIM)")

    if conditional:
        gen.line("endif()")


def _emit_staging_target_dependencies(gen: CMakeGenerator, module_registry: ModuleRegistry) -> None:
    for module_name in module_registry.topological_sort():
        module = module_registry.find(module_name)
        if module is None or module.module_type in (ModuleType.GITCLONE, ModuleType.BINARY):
            continue
        gen.line(
            f"if(TARGET yae_reconcile_staging AND TARGET {module.cmake_target_name})"
        )
        gen.line(f"    add_dependencies({module.cmake_target_name} yae_reconcile_staging)")
        gen.line("endif()")


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
