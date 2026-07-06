from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from collections.abc import Sequence
import argparse
import json
import os
import shutil
import subprocess

from yae.make_project_files import generate_project_files
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


def get_project_dir(args: argparse.Namespace) -> Path:
    return args.project_dir.resolve()


def get_build_dir_override(args: argparse.Namespace) -> Path | None:
    build_dir = getattr(args, "build_dir", None)
    return build_dir.resolve() if build_dir else None


def run_project_file_generation(project_dir: Path, external_modules_dir: Path | None) -> None:
    logger.info("Generating CMake files for %s", project_dir)
    generate_project_files(project_dir=project_dir, external_modules_dir=external_modules_dir)


def read_project_config(project_dir: Path) -> dict:
    with open(project_dir / "yae_project.json", mode="r", encoding="utf-8") as file:
        return json.load(file)


def merge_config(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result


def resolve_project_path(project_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_dir / path


def resolve_config_value(project_dir: Path, value: object) -> str:
    if not isinstance(value, str):
        return str(value)
    return value.replace("${project_dir}", project_dir.as_posix())


def get_default_configuration(project_dir: Path) -> dict:
    project_config = read_project_config(project_dir)
    default_configuration = project_config.get("default_configuration", {})

    local_config_path = project_dir / "local-config.json"
    if not local_config_path.exists():
        return default_configuration

    logger.info("Applying local configuration from %s", local_config_path)
    with open(local_config_path, mode="r", encoding="utf-8") as file:
        local_config = json.load(file)

    local_default_configuration = local_config.get("default_configuration", local_config)
    return merge_config(default_configuration, local_default_configuration)


def should_resolve_environment_path(name: str, value: str) -> bool:
    return name.endswith("_DIR") and not shutil.which(value)


def get_build_dir(project_dir: Path, build_dir_override: Path | None) -> Path:
    if build_dir_override is not None:
        return build_dir_override
    default_configuration = get_default_configuration(project_dir)
    return resolve_project_path(project_dir, default_configuration.get("build_dir", "build"))


def run_cmake_configure(
    project_dir: Path,
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
    command.extend(extra_cmake_args)

    run_subprocess(command, env=environment)
