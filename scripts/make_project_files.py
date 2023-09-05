"""Generates CMakeLists.txt files to build the project"""

from pathlib import Path
import json
from typing import Iterable, Callable, Generator
import enum
import collections
import subprocess

from cmake_generator import CMakeGenerator
from yae import *


class ModuleRegistry:
    def __init__(self):
        self.__lookup: dict[str, Module] = dict()

    def find(self, module_name: str) -> Module | None:
        return self.__lookup.get(module_name, None)

    def add(self, modules: Iterable[Module]) -> bool:
        """Add module objects to the registry. Ensures that all modules unique"""
        all_added = True
        for module in modules:
            if module.name in self.__lookup:
                first = self.__lookup[module.name]
                print(f"Found duplicate of {module.name} module name:")
                print(f"   {first.module_file_path.as_posix()} <- first occurence")
                print(f"   {module.module_file_path.as_posix()} <- duplicate")
                all_added = False
            self.__lookup[module.name] = module
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

    def toplogical_sort(self) -> list[str]:
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

        for node in self.__lookup:
            if node not in visited:
                dfs(node)

        # Reverse the result stack to get the topological ordering
        return result_stack


def main():
    ctx = GlobalContext()
    module_registry = ModuleRegistry()

    # Gather modules
    if not module_registry.add(map(Module, ctx.modules_dir.rglob("*.module.json"))):
        return

    if not module_registry.ensure_single_module_rules():
        return

    if not module_registry.ensure_dpependency_graph_is_valid():
        return

    # git clone --depth 1 --branch <tag_name> <repo_url>
    def initialize_git_module(module: Module):
        clone_dir = module.rel_cloned_repo_path(ctx)
        if not clone_dir.exists():
            subprocess.check_call(
                ["git", "clone", "--depth", "1", "--branch", module.git_tag, module.git_url, clone_dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    for module_name in module_registry.toplogical_sort():
        module = module_registry.find(module_name)
        if module.module_type == ModuleType.GITCLONE:
            initialize_git_module(module)

    yae_root_var = "YAE_ROOT"

    with open(CMakeGenerator.make_file_path(ctx.root_dir), mode="w", encoding="utf-8") as file:
        gen = CMakeGenerator(file)
        gen.version_line(3, 20)
        gen.line()
        gen.project_line("YAE")
        gen.line()
        gen.define_cpp_standard(20)
        gen.require_cpp_standard()
        gen.disable_cpp_extensions()
        gen.line()
        gen.add_module_path(Path("cmake"))
        gen.line()
        gen.line(f"set({yae_root_var} ${{CMAKE_CURRENT_SOURCE_DIR}})")
        gen.line()

        top_sorted = module_registry.toplogical_sort()

        for module_name in top_sorted:
            module = module_registry.find(module_name)
            if module.module_type == ModuleType.GITCLONE:
                # TODO: read configuration cmake variables for module
                gen.add_subdirectory(module.cmake_subdirectory(ctx))

        for module_name in top_sorted:
            module = module_registry.find(module_name)
            if module.module_type != ModuleType.GITCLONE:
                gen.add_subdirectory(module.cmake_subdirectory(ctx))

        gen.line()
        gen.line("enable_testing()")

    for module in (module_registry.find(module_name) for module_name in module_registry.toplogical_sort()):
        if module.module_type == ModuleType.GITCLONE:
            continue

        cmake_file_path = CMakeGenerator.make_file_path(module.root_dir)
        with open(cmake_file_path, mode="w", encoding="utf-8") as file:
            gen = CMakeGenerator(file)
            gen.version_line(3, 20)

            src_var_name = "module_source_files"

            rel_sources = sorted(path.relative_to(module.root_dir) for path in module.source_files)

            has_cpp_files = any(any(path.suffix == suffix for suffix in CPP_SUFFIXES) for path in rel_sources)
            is_interface_library = False

            gen.include("set_compiler_options")
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
                def convert(module: str) -> str:
                    return module_registry.find(module).cmake_target_name

                return list(map(convert, modules))

            gen.line(f"set_generic_compiler_options({module.name} {private_access})")
            gen.target_link_libraries(module.name, private_access, to_cmake_modules(module.public_dependencies))
            gen.target_link_libraries(module.name, public_access, to_cmake_modules(module.private_dependencies))
            gen.target_include_directories(module.name, public_access, [Path("code/public")])
            gen.target_include_directories(module.name, private_access, [Path("code/private")])

            if module.enable_testing:
                gen.line("enable_testing()")
                gen.line("include(GoogleTest)")
                gen.line(f"gtest_discover_tests({module.name})")


if __name__ == "__main__":
    main()
