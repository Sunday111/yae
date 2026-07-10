from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from collections.abc import Sequence
import os
import shutil
import subprocess

from yae import yae_constants
from yae.cmake_project import generate_project_files
from yae.errors import ProjectError
from yae.local_config import get_default_configuration
from yae.module import Module
from yae.module import ModuleType
from yae.resolver import ResolvedProject
from yae.resolver import resolve_project
from yae.settings import ResolvedSettings
from yae.yae_logging import get_logger


logger = get_logger(__name__)
subprocess_logger = get_logger("subprocess")


def run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    subprocess_logger.info("$ %s", " ".join(command))
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdout is not None
    for line in process.stdout:
        subprocess_logger.info("%s", line.rstrip())

    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)


def _has_local_executable_module(project_dir: Path, module_name: str) -> bool:
    excluded_dir_names = {yae_constants.DEFAULT_BUILD_DIR_NAME, yae_constants.CLONED_REPOSITORIES_DIRECTORY_NAME}
    for module_file in project_dir.rglob(f"{module_name}{yae_constants.MODULE_EXT}"):
        if excluded_dir_names & set(module_file.relative_to(project_dir).parts):
            continue
        if Module(module_file).module_type == ModuleType.EXECUTABLE:
            return True
    return False


def find_cloned_project_dirs(cloned_repositories_dir: Path) -> list[Path]:
    """Finds immediate `owner/repo` project checkouts under a cloned repositories
    root (the layout `yae clone` produces)."""
    if not cloned_repositories_dir.is_dir():
        return []
    pattern = f"*/*/{yae_constants.PROJECT_CONFIG_FILE_NAME}"
    return [project_file.parent for project_file in sorted(cloned_repositories_dir.glob(pattern))]


def find_project_dir_by_run_target(cloned_repositories_dir: Path, run_target: str) -> Path | None:
    """Searches immediate `owner/repo` checkouts under a cloned repositories root
    (the layout `yae clone` produces) for one that locally declares an executable
    module named `run_target`, without resolving any project's dependencies.
    """
    candidates = [
        project_dir
        for project_dir in find_cloned_project_dirs(cloned_repositories_dir)
        if _has_local_executable_module(project_dir, run_target)
    ]

    if len(candidates) > 1:
        joined = ", ".join(candidate.as_posix() for candidate in candidates)
        raise ProjectError(
            f"Multiple cloned projects under {cloned_repositories_dir} provide an executable named "
            f"'{run_target}': {joined}. Use --project_dir to disambiguate."
        )

    return candidates[0] if candidates else None


def run_project_file_generation(
    project_dir: Path,
    cloned_repositories_dir: Path | None,
    show_clone_progress: bool = False,
    resolved_project: ResolvedProject | None = None,
) -> None:
    logger.info("Generating CMake files for %s", project_dir)
    generate_project_files(
        project_dir=project_dir,
        cloned_repositories_dir=cloned_repositories_dir,
        show_clone_progress=show_clone_progress,
        resolved_project=resolved_project,
    )


def resolve_project_path(project_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_dir / path


def resolve_config_value(project_dir: Path, value: object) -> str:
    if not isinstance(value, str):
        return str(value)
    return value.replace("${project_dir}", project_dir.as_posix())


def should_resolve_environment_path(name: str, value: str) -> bool:
    return name.endswith("_DIR") and not shutil.which(value)


def get_build_dir(project_dir: Path, build_dir_override: Path | None) -> Path:
    if build_dir_override is not None:
        return build_dir_override
    default_configuration = get_default_configuration(project_dir)
    return resolve_project_path(project_dir, default_configuration.get("build_dir", yae_constants.DEFAULT_BUILD_DIR_NAME))


def find_executable_module(
    project_dir: Path,
    cloned_repositories_dir: Path | None,
    module_name: str,
    show_clone_progress: bool = False,
) -> Module | None:
    resolved_project = resolve_project(
        project_dir=project_dir,
        cloned_repositories_dir=cloned_repositories_dir,
        show_clone_progress=show_clone_progress,
    )
    module = resolved_project.module_registry.find(module_name)
    if module is None or module.module_type != ModuleType.EXECUTABLE:
        return None
    return module


def run_cmake_configure(
    project_dir: Path,
    cloned_repositories_dir: Path | None,
    build_dir_override: Path | None,
    extra_cmake_args: list[str],
) -> None:
    default_configuration = get_default_configuration(project_dir)
    build_dir = get_build_dir(project_dir, build_dir_override)
    logger.info("Configuring CMake project in %s", build_dir)

    environment = os.environ.copy()
    for name, value in default_configuration.get("environment", {}).items():
        resolved_value = resolve_config_value(project_dir, value)
        if should_resolve_environment_path(name, resolved_value):
            resolved_value = resolve_project_path(project_dir, resolved_value).as_posix()
            Path(resolved_value).mkdir(parents=True, exist_ok=True)
        environment[name] = resolved_value

    command = ["cmake", "-S", project_dir.as_posix(), "-B", build_dir.as_posix()]
    if generator := default_configuration.get("generator"):
        command.extend(["-G", str(generator)])

    definitions = dict(default_configuration.get("cmake_definitions", {}))
    command.extend(f"-D{name}={resolve_config_value(project_dir, value)}" for name, value in definitions.items())
    settings = ResolvedSettings.from_project(project_dir, cloned_repositories_dir)
    command.append(f"-DYAE_CLONED_REPOSITORIES_DIR={settings.cloned_repositories_dir.as_posix()}")
    command.extend(extra_cmake_args)

    run_subprocess(command, env=environment)
