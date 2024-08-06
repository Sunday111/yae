"""Generates CMakeLists.txt files to build the project"""

from pathlib import Path
from typing import Iterable, Callable, Generator
import collections
import argparse

from cmake_generator import CMakeGenerator
from cloned_repo_registry import ClonedRepoRegistry
from global_context import GlobalContext
import yae_module
from yae_module import Module
from yae_module import ModuleType
import json_utils


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

    ctx = GlobalContext(project_root=cli_parameters.project_dir)
    module_registry = ModuleRegistry()
    cloned_repo_registry = ClonedRepoRegistry(ctx)

    modules_dirs_queue: list[Path] = list(ctx.all_modules_dirs)
    packages_queue: list[tuple[str, str]] = list()  # list of tuples. first item is git url, second is tag

    all_modules_ok = True

    def add_package(package_uri: str, package_tag: str):
        nonlocal all_modules_ok
        prefix = "https://github.com/"
        if not package_uri.startswith(package_uri):
            all_modules_ok = False
            print(f"Unexpected module uri. Should start with {prefix}")
            return

        subdir = package_uri.replace(prefix, "")
        if len(subdir) == 0:
            all_modules_ok = False
            print(f"Unexpected module uri. Expected to contain repository path after {prefix}")
            return

        if cloned_repo_registry.exists_and_same_ref(subdir, package_uri, package_tag):
            return

        subdir = Path(subdir)
        if not cloned_repo_registry.fetch_repo(subdir, package_uri, package_tag):
            print(f"Failed to clone this uri: {package_uri}. Check it exists and has {package_tag} branch or tag")
            all_modules_ok = False

        full_package_package_path = ctx.project_config.cloned_repos_dir / subdir
        modules_dirs_queue.append(full_package_package_path)

        for package_json_path in list(full_package_package_path.rglob("*.package.json")):
            package_json = json_utils.read_json_file(package_json_path)
            dependencies: dict = package_json.get("Dependencies", dict())
            git_packages: list[str] = dependencies.get("GitPackages", list())
            for git_dep in git_packages:
                packages_queue.append((git_dep, "main"))

    def add_module(module: Module):
        nonlocal all_modules_ok
        if not module_registry.add_one(module):
            all_modules_ok = False
            return

        for package_uri in module.git_packages:
            packages_queue.append((package_uri, "main"))

        if module.module_type == ModuleType.GITCLONE:
            if not cloned_repo_registry.fetch_repo(module.local_path, module.git_url, module.git_tag):
                all_modules_ok = False
                return

    while modules_dirs_queue or packages_queue:
        while modules_dirs_queue:
            modules_dir = modules_dirs_queue.pop()
            for module_file_path in modules_dir.rglob("*.module.json"):
                module = Module(module_file_path)
                add_module(module)
        while packages_queue:
            git_url, tag = packages_queue.pop()
            add_package(git_url, tag)

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
        for copy_dir in module.post_build_copy_dirs:
            gen.line(f"add_custom_command(TARGET {module.cmake_target_name}")
            gen.line(f"    POST_BUILD COMMAND ${{CMAKE_COMMAND}} -E copy_directory")
            gen.line(f'    "${{CMAKE_CURRENT_SOURCE_DIR}}/{copy_dir.relative_to(module.root_dir)}"')
            gen.line(f"    $<TARGET_FILE_DIR:{module.cmake_target_name}>/{copy_dir.stem})")

    with open(CMakeGenerator.make_file_path(ctx.root_dir), mode="w", encoding="utf-8") as file:
        gen = CMakeGenerator(file)
        gen.version_line(3, 20)
        gen.line()
        gen.project_line(ctx.project_config.name)
        gen.line()
        gen.define_cpp_standard(ctx.project_config.cpp_standard)
        gen.require_cpp_standard()
        gen.disable_cpp_extensions()
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
                if module.module_type == ModuleType.GITCLONE:
                    path = module.cmake_subdirectory(ctx)
                    if path not in added_subdirs:
                        gen.line(f"# {module.git_url} {module.git_tag}")
                        for variable_name, variable_value in module.cmake_options.items():
                            if not gen.option(variable_name, variable_value):
                                return

                        is_system = True
                        gen.add_subdirectory(path, is_system)
                        copy_after_build(gen, module)
                        gen.line()
                        added_subdirs.add(path)

        gen.header_comment(" Own Modules ")
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

            has_cpp_files = any(
                any(path.suffix == suffix for suffix in yae_module.CPP_SUFFIXES) for path in rel_sources
            )
            is_interface_library = False

            gen.include("set_compiler_options")
            if module.specifies_lto:
                gen.include("yae_lto")

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
            gen.target_link_libraries(module.name, public_access, to_cmake_modules(module.public_dependencies))
            gen.target_link_libraries(module.name, private_access, to_cmake_modules(module.private_dependencies))
            gen.target_include_directories(module.name, public_access, [Path("code/public")])
            gen.target_include_directories(module.name, private_access, [Path("code/private")])

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
