from __future__ import annotations

import collections
from typing import Iterable, Generator, Callable

from yae import yae_constants
from yae.module import Module
from yae.module import ModuleType
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class ModuleRegistry:
    def __init__(self):
        self.__lookup: dict[str, Module] = dict()

    def find(self, module_name: str) -> Module | None:
        return self.__lookup.get(module_name, None)

    def add_one(self, module: Module) -> bool:
        if module.name in self.__lookup:
            first = self.__lookup[module.name]
            logger.error(
                "Found duplicate of %s module name:\n   %s <- first occurrence\n   %s <- duplicate",
                module.name,
                first.module_file_path.as_posix(),
                module.module_file_path.as_posix(),
            )
            return False

        self.__lookup[module.name] = module

        return True

    def add(self, modules: Iterable[Module]) -> bool:
        """Add module objects to the registry. Ensures that all modules unique"""
        all_added = True
        for module in modules:
            if not self.add_one(module):
                all_added = False
        return all_added

    def ensure_dependency_graph_is_valid(self) -> bool:
        """Ensures dependency graph can be built without cycles"""

        if len(self.__lookup) == 0:
            logger.error("Empty set of modules")
            return False

        visited = collections.defaultdict(bool)
        stack_set: set[str] = set()
        stack: list[str] = list()

        def dfs(node: str) -> bool:
            """Returns true if there is cycle"""
            visited[node] = True
            stack.append(node)
            stack_set.add(node)
            for dependency in self.__lookup[node].all_dependencies:
                if not visited[dependency]:
                    if dfs(dependency):
                        return True
                elif dependency in stack_set:
                    cycle_walk = "\n".join(f"   {val}" for val in [*stack, dependency])
                    logger.error("There is a cycle in dependency graph. Walk list:\n%s", cycle_walk)
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

    def __all_dependencies_exist(self, module: Module) -> bool:
        for dep in module.all_dependencies:
            if dep not in self.__lookup:
                logger.error('"%s" depends on "%s", which does not exist', module.name, dep)
                return False
        return True

    def __has_valid_module_file_name(self, module: Module) -> bool:
        if module.module_type == ModuleType.GITCLONE:
            return True
        module_file_path = self.__lookup[module.name].module_file_path
        expected_file_name = f"{module.name}{yae_constants.MODULE_EXT}"
        if module_file_path.name != expected_file_name:
            logger.error(
                'Wrong module file name for "%s" module: "%s" (expected "%s")',
                module.name,
                module_file_path.name,
                expected_file_name,
            )
            return False
        return True

    def ensure_single_module_rules(self) -> bool:
        def all_rules() -> Generator[Callable[[Module], bool], None, None]:
            yield self.__all_dependencies_exist
            yield self.__has_valid_module_file_name

        all_ok = True
        for rule in all_rules():
            if not self.__ensure_single_module_rule(rule):
                all_ok = False

        return all_ok

    def topological_sort(self, targets: list[str] | None = None) -> list[str]:
        """Returns list of modules names sorted topologically.
        All modules in this list come before it's dependencies
        """

        visited: set[str] = set()
        result_stack: list[str] = []

        def dfs(node: str):
            visited.add(node)

            for neighbor in self.__lookup[node].all_dependencies:
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
