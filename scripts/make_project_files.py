"""Generates CMakeLists.txt files to build the project"""

from pathlib import Path
from typing import Iterable
import argparse

from cmake_generator import CMakeGenerator
from cloned_repository_registry import ClonedRepositoryRegistry
from global_context import GlobalContext
import yae_module
from yae_module import Module
from yae_module import ModuleType
import json_utils
import yae_module_registry
from yae_package import Package
from github_link import GitHubLink
import itertools


def gather_packages(ctx: GlobalContext, repo_registry: ClonedRepositoryRegistry) -> list[Package]:
    local_packages: dict[str, Package] = dict()
    available_packages: dict[str, tuple[Package, GitHubLink]] = dict()
    packages_to_fetch: list[tuple[str, GitHubLink]] = list()
    required_packages: set[str] = set()

    # collect local packages and their dependencies
    for package in ctx.project_config.packages:
        assert package.name not in local_packages
        local_packages[package.name] = package
        required_packages.add(package.name)
        for name, link in package.dependencies:
            if name in local_packages:
                assert link is None
                continue

            packages_to_fetch.append([name, link])

    while packages_to_fetch:
        name, link = packages_to_fetch.pop()
        required_packages.add(name)

        if name in local_packages:
            continue

        if name in available_packages:
            if link == available_packages[name]:
                # Package already fetched with the same link
                continue
            else:
                existing_package, existing_link = available_packages[name]
                raise RuntimeError(
                    f"Packages with the same address must be identical. Existing: {existing_link.url} {existing_link.tag} {existing_link.subdir}. New one: {link.url} {link.tag} {link.subdir}"
                )

        if not repo_registry.fetch_repo(link.subdir, link.url, link.tag):
            raise RuntimeError(f"Failed to fetch: {link.url}. Check it exists and has {link.tag} branch or tag")

        repo_root = ctx.project_config.cloned_repos_dir / link.subdir
        for package in Package.glob_in(repo_root):
            assert package.name not in available_packages
            available_packages[package.name] = (package, link)
            if package.name in required_packages:
                packages_to_fetch.extend(package.dependencies)

        # Ensure this package actually exists in that repository
        if name not in available_packages:
            raise RuntimeError(f"Could not find package {name} at {repo_root.as_posix()} ({link.url} {link.tag})")

    return list(
        filter(
            lambda x: x.name in required_packages,
            itertools.chain(local_packages.values(), (package for package, link in available_packages.values())),
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_dir", type=Path, required=True, help="Path to directory with your project")
    parser.add_argument(
        "--external_modules_dir", type=Path, required=False, help="Path to directory where external repositories live"
    )
    cli_parameters = parser.parse_args()

    project_dir: Path = cli_parameters.project_dir
    if not project_dir.is_absolute():
        project_dir.absolute()
    project_dir = project_dir.resolve()

    ctx = GlobalContext(project_root=project_dir, external_modules_dir=cli_parameters.external_modules_dir)
    cloned_repo_registry = ClonedRepositoryRegistry(ctx)
    packages = gather_packages(ctx, cloned_repo_registry)

    module_registry = yae_module_registry.ModuleRegistry()
    add_module_errors: list[str] = list()

    def add_module(module: Module):
        if not module_registry.add_one(module):
            add_module_errors.append(f"Failed to add module {module.root_dir.as_posix()} from package {package.name}")
        if module.module_type == ModuleType.GITCLONE:
            if not cloned_repo_registry.fetch_repo(module.local_path, module.git_url, module.git_tag):
                raise RuntimeError(
                    f"Failed to clone this uri: {module.git_url}. Check it exists and has {module.git_tag} branch or tag"
                )

    def add_modules(path: Path):
        for module in Module.sorted_glob_in(path):
            add_module(module)

    add_modules(ctx.yae_modules_dir)

    for package in packages:
        add_modules(package.modules_dir)

    if add_module_errors:
        for err in add_module_errors:
            print(err)
        return

    if not module_registry.ensure_single_module_rules():
        return

    if not module_registry.ensure_dpependency_graph_is_valid():
        return

    yae_root_var = "YAE_ROOT"
    project_root_var = "YAE_PROJECT_ROOT"

    def copy_after_build(gen: CMakeGenerator, module: Module):
        copy_dirs = list(sorted(module.post_build_copy_dirs))
        if len(copy_dirs) > 0:
            gen.line(f"add_custom_target({module.cmake_target_name}_copy_files ALL")
            for copy_dir in copy_dirs:
                command = f"    ${{CMAKE_COMMAND}} -E copy_directory"
                command += f' "${{CMAKE_CURRENT_SOURCE_DIR}}/{copy_dir.relative_to(module.root_dir)}"'
                command += f" ${{CMAKE_RUNTIME_OUTPUT_DIRECTORY}}/{copy_dir.stem}"
                gen.line(command)
            gen.line(")")
            gen.line(f"add_dependencies({module.cmake_target_name}_copy_files {module.cmake_target_name})")

    with open(CMakeGenerator.make_file_path(ctx.root_dir), mode="w", encoding="utf-8") as file:
        gen = CMakeGenerator(file)
        gen.version_line(3, 20)
        gen.line()
        gen.project_line(ctx.project_config.name)
        gen.line()
        gen.define_cpp_standard(ctx.project_config.cpp_standard)
        gen.require_cpp_standard()
        gen.disable_cpp_extensions()

        gen.line("# Set output directories for binaries")
        gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)")
        gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})")
        gen.line("# Set output directories for archives")
        gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)")
        gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})")
        gen.line("# Set output directories for libraries")
        gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)")
        gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})")
        gen.line("set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_DEBUG ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})")

        gen.line()
        external_modules_var_name = "YAE_EXTERNAL_MODULES_DIR"
        gen.line("# Set path to external modules sources")
        if ctx.project_config.cloned_repos_dir.is_relative_to(ctx.root_dir):
            gen.line(
                f"set({external_modules_var_name} ${{CMAKE_CURRENT_SOURCE_DIR}}/{ctx.project_config.cloned_repos_dir.relative_to(ctx.root_dir).as_posix()})"
            )

        gen.line()
        if ctx.yae_root_dir.is_relative_to(ctx.project_root_dir):
            # engine is part of the project
            project_rel_path = ctx.yae_root_dir.relative_to(ctx.project_root_dir)
            gen.line(f'set({yae_root_var} "${{CMAKE_CURRENT_SOURCE_DIR}}/{project_rel_path.as_posix()}")')
        else:
            # project is part of the engine
            gen.line(f'set({yae_root_var} "${{CMAKE_CURRENT_SOURCE_DIR}}")')

        gen.line(f'set({project_root_var} "${{CMAKE_CURRENT_SOURCE_DIR}}")')
        gen.line(f'set(CMAKE_MODULE_PATH "${{CMAKE_MODULE_PATH}};${{{yae_root_var}}}/cmake")')
        gen.line()
        gen.line()

        if not (ctx.project_config.enable_lto_globally is None):
            gen.include("yae_lto")
            gen.line("enable_lto_globally()" if ctx.project_config.enable_lto_globally else "disable_lto_globally()")

        gen.line()
        gen.line()

        top_sorted = module_registry.toplogical_sort()

        added_subdirs: set[str] = set()
        for module_name in top_sorted:
            module = module_registry.find(module_name)

            module_local_path: Path = None
            module_sources_path: str = None
            if module.module_type == ModuleType.GITCLONE:
                module_local_path = Path(module.local_path)
                module_sources_path = f"${{{external_modules_var_name}}}/{module_local_path.as_posix()}"
            else:
                if module.root_dir.is_absolute() and module.root_dir.is_relative_to(ctx.root_dir):
                    module_local_path = module.root_dir.relative_to(ctx.root_dir)
                    module_sources_path = module_local_path.as_posix()
                else:
                    module_local_path = module.root_dir.relative_to(ctx.project_config.cloned_repos_dir)
                    module_sources_path = f"${{{external_modules_var_name}}}/{module_local_path.as_posix()}"

            if module_sources_path in added_subdirs:
                continue

            variable_with_path_to_module = f"YAE_{module.name}_SOURCES"
            if module.module_type == ModuleType.GITCLONE:
                gen.line(f"# {module.git_url} {module.git_tag}")
            gen.line(f"set({variable_with_path_to_module} {module_sources_path})")

            if module.should_add_sbudirectory:
                for variable_name, variable_value in module.cmake_options.items():
                    if not gen.option(variable_name, variable_value):
                        return

                gen.add_subdirectory(
                    f"${{{variable_with_path_to_module}}}",
                    is_system=True,
                    exclude_from_all=module.cmake_exclude_from_all,
                    build_directory=f"yae_modules/{module_local_path.as_posix()}",
                )
                # copy_after_build(gen, module)
                gen.line()
                added_subdirs.add(module_sources_path)

        gen.line()
        gen.line("enable_testing()")

    for module in (module_registry.find(module_name) for module_name in module_registry.toplogical_sort()):
        if module.module_type == ModuleType.GITCLONE:
            continue

        if not module.generate_cmake_file:
            continue

        cmake_file_path = CMakeGenerator.make_file_path(module.root_dir)
        with open(cmake_file_path, mode="w", encoding="utf-8") as file:
            gen = CMakeGenerator(file)
            gen.version_line(3, 20)

            rel_sources = sorted(path.relative_to(module.root_dir) for path in module.source_files)

            has_cpp_files = any(path.suffix in yae_module.CPP_SUFFIXES for path in rel_sources)
            has_cuda_files = any(path.suffix in yae_module.CUDA_SUFFIXES for path in rel_sources)
            is_interface_library = False

            if has_cuda_files:
                gen.line("enable_language(CUDA)")

            gen.include("set_compiler_options")
            if module.specifies_lto:
                gen.include("yae_lto")

            src_var_name = "module_source_files"
            gen.make_paths_list_variable(src_var_name, rel_sources)

            if module.module_type == ModuleType.LIBRARY:
                lib_type = "STATIC"
                if not has_cpp_files:
                    lib_type = "INTERFACE"
                    is_interface_library = True
                gen.add_library(module.name, lib_type, src_var_name)
            elif module.module_type == ModuleType.EXECUTABLE:
                assert has_cpp_files
                gen.add_executable(module.name, src_var_name)
            else:
                print("Internal error. Unhandled module type: ", module.module_type)

            public_access = "PUBLIC"
            private_access = "PRIVATE"
            if is_interface_library:
                public_access = "INTERFACE"
                private_access = public_access

            def to_cmake_modules(modules: Iterable[str]) -> list[str]:
                result = list()
                for name in modules:
                    module = module_registry.find(name)
                    if len(module.cmake_modular_tragets) > 0:
                        result.extend(module.cmake_modular_tragets)
                    else:
                        result.append(module.cmake_target_name)

                return result

            gen.line(f"set_generic_compiler_options({module.name} {private_access})")
            gen.target_link_libraries(module.name, public_access, to_cmake_modules(module.public_dependencies))
            gen.target_link_libraries(module.name, private_access, to_cmake_modules(module.private_dependencies))
            gen.target_include_directories(module.name, public_access, [Path("code/public")])
            gen.target_include_directories(module.name, private_access, [Path("code/private")])

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

            copy_after_build(gen, module)


if __name__ == "__main__":
    main()
