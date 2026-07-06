from __future__ import annotations

import argparse

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_external_modules_dir_argument
from yae.commands.base import add_project_dir_argument
from yae.commands.common import get_project_dir
from yae.module import Module
from yae.module import ModuleType
from yae.resolver import ModuleOrigin
from yae.resolver import resolve_project


class ListCommand(Command):
    name = "list"
    help = "List project modules"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_external_modules_dir_argument(parser)

        filters = parser.add_mutually_exclusive_group()
        filters.add_argument("-e", "--executables", action="store_true", help="List executable modules only")
        filters.add_argument("-l", "--libraries", action="store_true", help="List library modules only")

        origin_filters = parser.add_mutually_exclusive_group()
        origin_filters.add_argument("--project", action="store_true", help="List project modules only")
        origin_filters.add_argument("--support", action="store_true", help="List yae-support modules only")
        origin_filters.add_argument("--external", action="store_true", help="List external package modules only")
        origin_filters.add_argument("--all", action="store_true", help="List modules from every origin")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = get_project_dir(args)
        external_modules_dir = args.external_modules_dir.resolve() if args.external_modules_dir else None
        resolved_project = resolve_project(project_dir=project_dir, external_modules_dir=external_modules_dir)
        module_registry = resolved_project.module_registry

        modules = [module_registry.find(name) for name in module_registry.toplogical_sort()]
        modules = [module for module in modules if module is not None]
        modules = [
            module
            for module in modules
            if self._should_show_module(module, resolved_project.module_origins[module.name], args)
        ]

        for module in modules:
            origin = resolved_project.module_origins[module.name]
            print(f"{origin.value:8} {module.module_type.name.lower():10} {module.name}")

    def _should_show_module(self, module: Module, origin: ModuleOrigin, args: argparse.Namespace) -> bool:
        if module.module_type == ModuleType.GITCLONE:
            return False
        if args.executables:
            if module.module_type != ModuleType.EXECUTABLE:
                return False
        if args.libraries:
            if module.module_type != ModuleType.LIBRARY:
                return False

        if args.all:
            return True
        if args.support:
            return origin == ModuleOrigin.SUPPORT
        if args.external:
            return origin == ModuleOrigin.EXTERNAL
        return origin == ModuleOrigin.PROJECT
