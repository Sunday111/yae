from __future__ import annotations

import argparse

from yae.cloned_repository_registry import ClonedRepositoryRegistry
from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_external_modules_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import get_project_dir
from yae.global_context import GlobalContext
from yae.make_project_files import gather_modules
from yae.make_project_files import gather_packages
from yae.yae_module import Module
from yae.yae_module import ModuleType


class ListCommand(Command):
    name = "list"
    help = "List project modules"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_external_modules_dir_argument(parser)

        filters = parser.add_mutually_exclusive_group()
        filters.add_argument("-e", "--executables", action="store_true", help="List executable modules only")
        filters.add_argument("-l", "--libraries", action="store_true", help="List library modules only")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = get_project_dir(args)
        external_modules_dir = args.external_modules_dir.resolve() if args.external_modules_dir else None
        global_context = GlobalContext(project_root=project_dir, external_modules_dir=external_modules_dir)
        repo_registry = ClonedRepositoryRegistry(global_context)
        packages = gather_packages(global_context, repo_registry)
        module_registry = gather_modules(global_context, packages, repo_registry)

        modules = [module_registry.find(name) for name in module_registry.toplogical_sort()]
        modules = [module for module in modules if module is not None]
        modules = [module for module in modules if self._should_show_module(module, args)]

        for module in modules:
            print(f"{module.module_type.name.lower():10} {module.name}")

    def _should_show_module(self, module: Module, args: argparse.Namespace) -> bool:
        if module.module_type == ModuleType.GITCLONE:
            return False
        if args.executables:
            return module.module_type == ModuleType.EXECUTABLE
        if args.libraries:
            return module.module_type == ModuleType.LIBRARY
        return True
