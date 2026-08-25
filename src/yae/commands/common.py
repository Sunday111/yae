from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from collections.abc import Sequence
from typing import TextIO
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

LINKER_TYPES = {
    "mold": "MOLD",
    "lld": "LLD",
    "ld": "BFD",
}

LINKER_CANDIDATES = (
    ("mold", "mold"),
    ("ld.lld", "lld"),
    ("ld", "ld"),
)


def resolve_linker_type(linker: object) -> str:
    linker_name = str(linker).lower()
    if linker_name not in LINKER_TYPES:
        supported_linkers = ", ".join(LINKER_TYPES)
        raise ProjectError(f"Unknown linker '{linker}'. Expected one of: {supported_linkers}")
    return LINKER_TYPES[linker_name]


def find_preferred_linker_type() -> str | None:
    for executable, linker_name in LINKER_CANDIDATES:
        if shutil.which(executable) is not None:
            return resolve_linker_type(linker_name)
    return None


def command_with_discrete_gpu(command: Sequence[str]) -> tuple[list[str], dict[str, str]]:
    environment = os.environ.copy()
    if shutil.which("prime-run") is not None:
        logger.info("Using prime-run for NVIDIA GPU offload")
        return ["prime-run", *command], environment

    logger.info("Using NVIDIA PRIME environment variables")
    environment.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
    environment.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    environment.setdefault("__VK_LAYER_NV_optimus", "NVIDIA_only")
    return list(command), environment


def run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
) -> None:
    subprocess_logger.info("$ %s", " ".join(command))
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=stdout if stdout is not None else subprocess.PIPE,
        stderr=subprocess.PIPE if stdout is not None else subprocess.STDOUT,
        text=True,
    )
    process_output = process.stderr if stdout is not None else process.stdout
    assert process_output is not None
    for line in process_output:
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
    """Finds `{owner/repo}/{ref}` project checkouts directly under a cloned
    repositories root (the shared layout both `yae clone` and dependency
    resolution produce), ignoring anything nested more deeply."""
    if not cloned_repositories_dir.is_dir():
        return []
    pattern = f"*/*/*/{yae_constants.PROJECT_CONFIG_FILE_NAME}"
    return [project_file.parent for project_file in sorted(cloned_repositories_dir.glob(pattern))]


def find_project_dir_by_run_target(cloned_repositories_dir: Path, run_target: str) -> Path | None:
    """Searches `{owner/repo}/{ref}` checkouts under a cloned repositories root
    (the shared layout both `yae clone` and dependency resolution produce) for one
    that locally declares an executable module named `run_target`, without
    resolving any project's dependencies.
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
        environment[name] = resolve_config_value(project_dir, value)

    command = ["cmake", "-S", project_dir.as_posix(), "-B", build_dir.as_posix()]
    has_cli_generator = any(arg == "-G" or arg.startswith("-G") for arg in extra_cmake_args)
    if not has_cli_generator:
        generator = default_configuration.get("generator") or "Ninja"
        command.extend(["-G", str(generator)])

    definitions = dict(default_configuration.get("cmake_definitions", {}))
    definitions.setdefault("CMAKE_EXPORT_COMPILE_COMMANDS", "ON")
    has_cli_linker_type = any(arg.startswith("-DCMAKE_LINKER_TYPE=") for arg in extra_cmake_args)
    if "CMAKE_LINKER_TYPE" not in definitions and not has_cli_linker_type:
        configured_linker = default_configuration.get("linker")
        if configured_linker is not None:
            linker_type = resolve_linker_type(configured_linker)
        else:
            linker_type = find_preferred_linker_type()
        if linker_type is not None:
            definitions["CMAKE_LINKER_TYPE"] = linker_type
    command.extend(f"-D{name}={resolve_config_value(project_dir, value)}" for name, value in definitions.items())
    settings = ResolvedSettings.from_project(project_dir, cloned_repositories_dir)
    command.append(f"-DYAE_CLONED_REPOSITORIES_DIR={settings.cloned_repositories_dir.as_posix()}")
    command.extend(extra_cmake_args)

    run_subprocess(command, env=environment)
