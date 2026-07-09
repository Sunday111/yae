from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yae.global_context import GlobalContext
from yae.module import Module
from yae.module import ModuleType


@dataclass(frozen=True)
class ModuleSourcePath:
    local_path: Path
    cmake_path: str


class CMakePathResolver:
    cloned_repositories_var_name = "YAE_CLONED_REPOSITORIES_DIR"
    project_root_var_name = "YAE_PROJECT_ROOT"
    support_root_var_name = "YAE_SUPPORT_ROOT"

    def __init__(self, ctx: GlobalContext):
        self.ctx = ctx

    def source_path(self, path: Path, *, prefer_project_root: bool = False) -> str:
        path = path.resolve()
        if prefer_project_root and path.is_relative_to(self.ctx.root_dir) and not path.is_relative_to(
            self.ctx.project_config.default_cloned_repositories_dir
        ):
            rel_path = path.relative_to(self.ctx.root_dir)
            return f"${{CMAKE_CURRENT_SOURCE_DIR}}/{rel_path.as_posix()}"
        if path.is_relative_to(self.ctx.project_config.cloned_repositories_dir):
            rel_path = path.relative_to(self.ctx.project_config.cloned_repositories_dir)
            return f"${{{self.cloned_repositories_var_name}}}/{rel_path.as_posix()}"
        if (
            path.is_relative_to(self.ctx.root_dir)
            and not path.is_relative_to(self.ctx.project_config.default_cloned_repositories_dir)
        ):
            rel_path = path.relative_to(self.ctx.root_dir)
            return f"${{CMAKE_CURRENT_SOURCE_DIR}}/{rel_path.as_posix()}"
        return path.as_posix()

    def module_source_path(self, module: Module, *, prefer_project_root: bool = False) -> ModuleSourcePath:
        if module.module_type == ModuleType.GITCLONE:
            module_local_path = Path(module.local_path)
            module_sources_path = f"${{{self.cloned_repositories_var_name}}}/{module_local_path.as_posix()}"
            return ModuleSourcePath(local_path=module_local_path, cmake_path=module_sources_path)

        if (
            prefer_project_root
            and module.root_dir.is_absolute()
            and module.root_dir.is_relative_to(self.ctx.root_dir)
            and not module.root_dir.is_relative_to(self.ctx.project_config.default_cloned_repositories_dir)
        ):
            module_local_path = module.root_dir.relative_to(self.ctx.root_dir)
            return ModuleSourcePath(local_path=module_local_path, cmake_path=module_local_path.as_posix())

        if module.root_dir.is_absolute() and module.root_dir.is_relative_to(self.ctx.project_config.cloned_repositories_dir):
            module_local_path = module.root_dir.relative_to(self.ctx.project_config.cloned_repositories_dir)
            module_sources_path = f"${{{self.cloned_repositories_var_name}}}/{module_local_path.as_posix()}"
            return ModuleSourcePath(local_path=module_local_path, cmake_path=module_sources_path)

        if (
            module.root_dir.is_absolute()
            and module.root_dir.is_relative_to(self.ctx.root_dir)
            and not module.root_dir.is_relative_to(self.ctx.project_config.default_cloned_repositories_dir)
        ):
            module_local_path = module.root_dir.relative_to(self.ctx.root_dir)
            return ModuleSourcePath(local_path=module_local_path, cmake_path=module_local_path.as_posix())

        return ModuleSourcePath(local_path=module.root_dir, cmake_path=module.root_dir.as_posix())

    def emit_default_cloned_repositories_dir(self) -> str:
        rel_path = self.ctx.project_config.default_cloned_repositories_dir.relative_to(self.ctx.root_dir)
        return f"${{CMAKE_CURRENT_SOURCE_DIR}}/{rel_path.as_posix()}"
