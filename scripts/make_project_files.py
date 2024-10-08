"""Generates CMakeLists.txt files to build the project"""

from pathlib import Path
from typing import Iterable, Callable, Generator
import typing
import collections
import argparse

from cmake_generator import CMakeGenerator
from cloned_repo_registry import ClonedRepoRegistry
from global_context import GlobalContext
import yae_module
from yae_module import Module
from yae_module import ModuleType
import json_utils
from dataclasses import dataclass


@dataclass
class GitHubLink:
    url: str
    tag: str
    subdir: Path

    @staticmethod
    def parse(link: str) -> "GitHubLink":
        prefix = "https://github.com/"
        default_tag = "main"
        if link.startswith(prefix):
            tokens = link.replace(prefix, "").split(" ")

            if len(tokens) == 1:
                return GitHubLink(url=prefix + tokens[0], tag=default_tag, subdir=Path(tokens[0]))

            if len(tokens) == 2:
                return GitHubLink(url=prefix + tokens[0], tag=tokens[1], subdir=Path(tokens[0]))

        print(f"Unexpected github link. Format: {prefix}your_repo tag. Tag is optional, {default_tag} is default")
        return None


class ModuleRegistry:
    def __init__(self):
        self.__lookup: dict[str, Module] = dict()
        self.__has_external_dependencies = False

    def find(self, module_name: str) -> Module | None:
        return self.__lookup.get(module_name, None)

    def add_one(self, module: Module) -> bool:
        if module.name in self.__lookup:
            first = self.__lookup[module.name]
            print(f"Found duplicate of {module.name} module name:")
            print(f"   {first.module_file_path.as_posix()} <- first occurence")
            print(f"   {module.module_file_path.as_posix()} <- duplicate")
            return False

        self.__lookup[module.name] = module

        if module.module_type == ModuleType.GITCLONE:
            self.__has_external_dependencies = True

        return True

    def add(self, modules: Iterable[Module]) -> bool:
        """Add module objects to the registry. Ensures that all modules unique"""
        all_added = True
        for module in modules:
            if not self.add_one(module):
                all_added = False
        return all_added

    def ensure_dpependency_graph_is_valid(self) -> bool:
        """Ensures dependncy graph can be built without cycles"""

        if len(self.__lookup) == 0:
            print("Empty set of modules")
            return False

        visited = collections.defaultdict(bool)
        stack_set: set[str] = set()
        stack: list[str] = list()

        def dfs(node: str) -> bool:
            """Returns true if there is cycle"""
            visited[node] = True
            stack.append(node)
            stack_set.add(node)
            for dependnency in self.__lookup[node].all_depepndencies:
                if not visited[dependnency]:
                    if dfs(dependnency):
                        return True
                elif dependnency in stack_set:
                    print("There is a cycle in dependency graph. Walk list: ")
                    stack.append(dependnency)
                    for val in stack:
                        print(f"   {val}")
                    stack.pop()
                    return True

            stack_set.remove(node)
            assert stack[-1] == node
            stack.pop()

            return False

        if any(not visited[node] and dfs(node) for node in self.__lookup):
            return False

        return True

    def __ensure_single_module_rule(self, is_valid_module: Callable[[Module], bool]) -> bool:
        all_ok = True
        for module in self.__lookup.values():
            if not is_valid_module(module):
                all_ok = False
        return all_ok

    def __all_dependnecies_exist(self, module: Module) -> bool:
        for dep in module.all_depepndencies:
            if dep not in self.__lookup:
                print(f'"{module.name}" depends on "{dep}", which does not exist')
                return False
        return True

    def __has_valid_module_file_name(self, module: Module) -> bool:
        if module.module_type == ModuleType.GITCLONE:
            return True
        module_file_path = self.__lookup[module.name].module_file_path
        expected_file_name = f"{module.name}.module.json"
        if module_file_path.name != expected_file_name:
            print(
                f"""Wrong module file name for \"{module.name}\" module: \"{module_file_path.name}\"
                Expected file name: \"{module_file_path.name}\""""
            )
            return False
        return True

    def ensure_single_module_rules(self) -> bool:
        def all_rules() -> Generator[Callable[[Module], bool], None, None]:
            yield self.__all_dependnecies_exist
            yield self.__has_valid_module_file_name

        all_ok = True
        for rule in all_rules():
            if not self.__ensure_single_module_rule(rule):
                all_ok = False

        return all_ok

    def toplogical_sort(self, targets: list[str] | None = None) -> list[str]:
        """Returns list of modules names sorted topologically.
        All modules in this list come before it's dependencies
        """

        visited: set[str] = set()
        result_stack: list[str] = []

        def dfs(node: str):
            visited.add(node)

            for neighbor in self.__lookup[node].all_depepndencies:
                if neighbor not in visited:
                    dfs(neighbor)

            # After visiting all neighbors, add the node to the result stack
            result_stack.append(node)

        if targets is None:
            targets = list(self.__lookup.keys())

        for node in targets:
            if node not in visited:
                dfs(node)

        # Reverse the result stack to get the topological ordering
        return result_stack

    @property
    def has_external_dependencies(self) -> bool:
        return self.__has_external_dependencies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_dir", type=Path, required=True, help="Path to directory with your project")
    cli_parameters = parser.parse_args()

    project_dir: Path = cli_parameters.project_dir
    if not project_dir.is_absolute():
        project_dir.absolute()
    project_dir = project_dir.resolve()

    ctx = GlobalContext(project_root=project_dir)
    module_registry = ModuleRegistry()
    cloned_repo_registry = ClonedRepoRegistry(ctx)

    modules_dirs_queue: list[Path] = list(ctx.all_modules_dirs)
    packages_queue: list[str] = list()  # list of package references

    all_modules_ok = True

    def add_package(package_reference: str):
        nonlocal all_modules_ok
        link = GitHubLink.parse(package_reference)
        if link is None:
            all_modules_ok = False
            return

        if not cloned_repo_registry.fetch_repo(link.subdir, link.url, link.tag):
            print(f"Failed to clone this uri: {link.url}. Check it exists and has {link.tag} branch or tag")
            all_modules_ok = False

        full_package_package_path = ctx.project_config.cloned_repos_dir / link.subdir
        modules_dirs_queue.append(full_package_package_path)

        for package_json_path in sorted(full_package_package_path.rglob("*.package.json")):
            package_json = json_utils.read_json_file(package_json_path)
            dependencies: dict = package_json.get("Dependencies", dict())
            git_packages: list[str] = dependencies.get("GitPackages", list())
            for git_dep in git_packages:
                packages_queue.append(git_dep)

    def add_module(module: Module):
        nonlocal all_modules_ok
        if not module_registry.add_one(module):
            all_modules_ok = False
            return

        for package_reference in module.git_packages:
            packages_queue.append(package_reference)

        if module.module_type == ModuleType.GITCLONE:
            if not cloned_repo_registry.fetch_repo(module.local_path, module.git_url, module.git_tag):
                all_modules_ok = False
                return

    while modules_dirs_queue or packages_queue:
        while modules_dirs_queue:
            modules_dir = modules_dirs_queue.pop()
            for module_file_path in sorted(modules_dir.rglob("*.module.json")):
                add_module(Module(module_file_path))
        while packages_queue:
            package_reference = packages_queue.pop()
            add_package(package_reference)

    if not all_modules_ok:
        print(f"Failed to add some modules")
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

        if module_registry.has_external_dependencies:
            added_subdirs: set[Path] = set()
            gen.header_comment(" External Dependencies ")
            gen.line()

            for module_name in top_sorted:
                module = module_registry.find(module_name)
                if module.module_type != ModuleType.GITCLONE:
                    continue

                path = module.cmake_subdirectory(ctx)
                if path in added_subdirs:
                    continue

                gen.line(f"# {module.git_url} {module.git_tag}")
                gen.line(f"set(YAE_CLONED_{module.name} ${{CMAKE_CURRENT_SOURCE_DIR}}/{path.as_posix()})")

                if module.should_add_sbudirectory:
                    for variable_name, variable_value in module.cmake_options.items():
                        if not gen.option(variable_name, variable_value):
                            return

                    gen.add_subdirectory(path, is_system=True, exclude_from_all=module.cmake_exclude_from_all)
                    copy_after_build(gen, module)
                    gen.line()
                    added_subdirs.add(path)

        gen.header_comment(" Own Modules ")
        for module_name in top_sorted:
            module = module_registry.find(module_name)
            if module.module_type != ModuleType.GITCLONE:
                gen.add_subdirectory(module.cmake_subdirectory(ctx), exclude_from_all=module.cmake_exclude_from_all)

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
