from __future__ import annotations

from pathlib import Path
import argparse
from rich.console import Console
from rich.table import Table

from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.commands.base import add_project_dir_argument
from yae import yae_constants
from yae.errors import ProjectError
from yae.commands.common import find_cloned_project_dirs
from yae.module import Module
from yae.module import ModuleType
from yae.resolver import ModuleOrigin
from yae.resolver import ResolvedProject


_MODULE_TYPE_ABBREVIATIONS = {
    ModuleType.EXECUTABLE: "exe",
    ModuleType.LIBRARY: "lib",
}


class ListCommand(Command):
    name = "list"
    help = "List project modules"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_project_dir_argument(parser)
        add_cloned_repositories_dir_argument(parser)

        filters = parser.add_mutually_exclusive_group()
        filters.add_argument("-e", "--executables", action="store_true", help="List executable modules only")
        filters.add_argument("-l", "--libraries", action="store_true", help="List library modules only")

        origin_filters = parser.add_mutually_exclusive_group()
        origin_filters.add_argument("--project", action="store_true", help="List project modules only")
        origin_filters.add_argument("--support", action="store_true", help="List yae-support modules only")
        origin_filters.add_argument("--external", action="store_true", help="List cloned package modules only")
        origin_filters.add_argument("--all", action="store_true", help="List modules from every origin")
        parser.add_argument("--plain", action="store_true", help="Print machine-readable rows without table formatting")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        project_dir = context.try_project_dir()
        if project_dir is not None:
            resolved_project = context.resolve_project(project_dir)
            modules_dir = resolved_project.context.project_config.cloned_repositories_dir
            rows = sorted(
                ((name, module_type) for name, module_type, _ in self._module_rows(resolved_project, args)),
                key=lambda row: row[0],
            )
            self._print_rows(modules_dir, rows, args, with_location_column=False)
            return

        if not args.all:
            raise ProjectError(
                f"Could not find {yae_constants.PROJECT_CONFIG_FILE_NAME}. Run this command from a YAE project "
                "directory, pass --project_dir, set YAE_PROJECT_DIR, or pass --all to list modules across every "
                "cloned project under YAE_CLONED_REPOSITORIES_DIR."
            )

        cloned_repositories_dir = context.cloned_repositories_dir_for_discovery()
        if cloned_repositories_dir is None:
            raise ProjectError(
                f"Could not find {yae_constants.PROJECT_CONFIG_FILE_NAME}, and no cloned repositories directory is "
                "known either. Pass --cloned_repositories_dir or set YAE_CLONED_REPOSITORIES_DIR."
            )

        candidate_dirs = find_cloned_project_dirs(cloned_repositories_dir)
        if not candidate_dirs:
            raise ProjectError(f"No cloned projects found under {cloned_repositories_dir}.")

        # Multiple cloned projects can share the same dependency (e.g. two projects
        # both depending on the same klgl checkout); dedupe by where the module's
        # source actually lives on disk, not by which project happened to resolve it.
        seen_locations: dict[Path, tuple[str, str, str]] = {}
        for candidate_dir in candidate_dirs:
            resolved_project = context.resolve_project(candidate_dir)
            for name, module_type, root_dir in self._module_rows(resolved_project, args):
                if root_dir in seen_locations:
                    continue
                try:
                    location = root_dir.relative_to(cloned_repositories_dir).as_posix()
                except ValueError:
                    location = root_dir.as_posix()
                seen_locations[root_dir] = (name, module_type, location)

        rows = sorted(seen_locations.values(), key=lambda row: row[0])
        self._print_rows(cloned_repositories_dir, rows, args, with_location_column=True)

    def _module_rows(self, resolved_project: ResolvedProject, args: argparse.Namespace) -> list[tuple[str, str, Path]]:
        module_registry = resolved_project.module_registry

        modules = [module_registry.find(name) for name in module_registry.topological_sort()]
        modules = [module for module in modules if module is not None]
        modules = [
            module
            for module in modules
            if self._should_show_module(module, resolved_project.module_origins[module.name], args)
        ]

        return [(str(module.name), _MODULE_TYPE_ABBREVIATIONS[module.module_type], module.root_dir) for module in modules]

    def _print_rows(
        self,
        modules_dir: Path,
        rows: list[tuple[str, ...]],
        args: argparse.Namespace,
        *,
        with_location_column: bool,
    ) -> None:
        if args.plain:
            print(f"Modules directory: {modules_dir}")
            for row in rows:
                if with_location_column:
                    name, module_type, location = row
                    print(f"{name:30} {module_type:3} {location}")
                else:
                    name, module_type = row
                    print(f"{name:30} {module_type}")
            return

        Console().print(f"Modules directory: {modules_dir}")
        table = Table(title="YAE Modules")
        table.add_column("Name", style="green")
        table.add_column("Type", style="magenta")
        if with_location_column:
            table.add_column("Location", style="yellow")
        for row in rows:
            table.add_row(*row)
        Console().print(table)

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
