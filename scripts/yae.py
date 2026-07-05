#!/usr/bin/env python3
"""Command-line entrypoint for yae."""

from pathlib import Path
import argparse
import json
import os
import runpy
import shutil
import subprocess
import sys


def print_help() -> None:
    print(
        """usage: yae <command> [args...]

commands:
  configure    Clone dependencies and configure CMake project
  build        Configure and build CMake targets
  run          Build and run the configured executable
  format       Apply clang-format to changed source files
  cleanup      Re-sync submodules and delete ignored files

Run `yae <command> --help` for command-specific help."""
    )


def run_project_file_generation(yae_root: Path, project_dir: Path, external_modules_dir: Path | None) -> None:
    script_path = yae_root / "scripts" / "make_project_files.py"
    args = [str(script_path), f"--project_dir={project_dir}"]
    if external_modules_dir is not None:
        args.append(f"--external_modules_dir={external_modules_dir}")

    old_argv = sys.argv
    old_path = list(sys.path)
    try:
        sys.path.insert(0, str(script_path.parent))
        sys.argv = args
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        sys.argv = old_argv
        sys.path = old_path


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
    yae_root: Path,
    project_dir: Path,
    build_dir_override: Path | None,
    extra_cmake_args: list[str],
) -> None:
    default_configuration = get_default_configuration(project_dir)
    build_dir = get_build_dir(project_dir, build_dir_override)

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
    definitions["YAE_ROOT"] = yae_root.as_posix()
    command.extend(f"-D{name}={resolve_config_value(project_dir, value)}" for name, value in definitions.items())
    command.extend(extra_cmake_args)

    subprocess.check_call(command, env=environment)


def run_configure(yae_root: Path, args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="yae configure",
        description="Clone dependencies, generate CMake project files, and configure the build directory",
    )
    parser.add_argument("--project_dir", type=Path, default=Path.cwd(), help="Path to directory with your project")
    parser.add_argument(
        "--external_modules_dir",
        type=Path,
        required=False,
        help="Path to directory where external repositories live",
    )
    parser.add_argument("--build_dir", type=Path, required=False, help="Override build directory")
    parser.add_argument("cmake_args", nargs=argparse.REMAINDER, help="Additional arguments passed to cmake")
    parsed = parser.parse_args(args)

    project_dir = parsed.project_dir.resolve()
    external_modules_dir = parsed.external_modules_dir.resolve() if parsed.external_modules_dir else None
    build_dir = parsed.build_dir.resolve() if parsed.build_dir else None
    cmake_args = parsed.cmake_args
    if cmake_args and cmake_args[0] == "--":
        cmake_args = cmake_args[1:]

    run_project_file_generation(yae_root, project_dir, external_modules_dir)
    run_cmake_configure(yae_root, project_dir, build_dir, cmake_args)


def configure_project_for_command(yae_root: Path, project_dir: Path, build_dir: Path | None) -> Path:
    run_project_file_generation(yae_root, project_dir, None)
    run_cmake_configure(yae_root, project_dir, build_dir, [])
    return get_build_dir(project_dir, build_dir)


def run_build(yae_root: Path, args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="yae build", description="Configure and build CMake targets")
    parser.add_argument("--project_dir", type=Path, default=Path.cwd(), help="Path to directory with your project")
    parser.add_argument("--build_dir", type=Path, required=False, help="Override build directory")
    parser.add_argument("targets", nargs="*", help="Targets to build instead of default build targets")
    parsed = parser.parse_args(args)

    project_dir = parsed.project_dir.resolve()
    build_dir = parsed.build_dir.resolve() if parsed.build_dir else None
    resolved_build_dir = configure_project_for_command(yae_root, project_dir, build_dir)

    default_configuration = get_default_configuration(project_dir)
    targets = parsed.targets or default_configuration.get("build_targets", [])
    if not targets:
        subprocess.check_call(["cmake", "--build", resolved_build_dir.as_posix(), "--parallel"])
        return

    for target in targets:
        subprocess.check_call(["cmake", "--build", resolved_build_dir.as_posix(), "--target", target, "--parallel"])


def run_with_discrete_gpu(command: list[str]) -> None:
    if shutil.which("prime-run") is not None:
        os.execvp("prime-run", ["prime-run", *command])

    os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
    os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    os.environ.setdefault("__VK_LAYER_NV_optimus", "NVIDIA_only")
    os.execv(command[0], command)


def run_app(yae_root: Path, args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="yae run", description="Build and run the configured executable")
    parser.add_argument("--project_dir", type=Path, default=Path.cwd(), help="Path to directory with your project")
    parser.add_argument("--build_dir", type=Path, required=False, help="Override build directory")
    parser.add_argument("run_target", nargs="?", help="Executable target to run instead of default run target")
    parser.add_argument("app_args", nargs=argparse.REMAINDER, help="Arguments passed to the executable")
    parsed = parser.parse_args(args)

    project_dir = parsed.project_dir.resolve()
    build_dir = parsed.build_dir.resolve() if parsed.build_dir else None
    default_configuration = get_default_configuration(project_dir)
    run_target = parsed.run_target or default_configuration.get("run_target")
    if not run_target:
        raise SystemExit("No run target was provided and default_configuration.run_target is not set")

    resolved_build_dir = configure_project_for_command(yae_root, project_dir, build_dir)
    subprocess.check_call(["cmake", "--build", resolved_build_dir.as_posix(), "--target", run_target, "--parallel"])

    copy_target = default_configuration.get("run_copy_target")
    if copy_target:
        subprocess.check_call(["cmake", "--build", resolved_build_dir.as_posix(), "--target", copy_target, "--parallel"])

    app_args = parsed.app_args
    if app_args and app_args[0] == "--":
        app_args = app_args[1:]
    app_path = resolved_build_dir / "bin" / run_target
    run_with_discrete_gpu([app_path.as_posix(), *app_args])


def run_format(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="yae format", description="Apply clang-format to changed source files")
    parser.add_argument("--project_dir", type=Path, default=Path.cwd(), help="Path to directory with your project")
    parser.add_argument("--tool", default="clang-format", help="clang-format executable")
    parsed = parser.parse_args(args)

    project_dir = parsed.project_dir.resolve()
    commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"],
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    changed_files: set[str] = set()
    for command in commands:
        output = subprocess.check_output(command, cwd=project_dir, text=True)
        changed_files.update(line for line in output.splitlines() if line)

    source_suffixes = {".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx"}
    files = sorted(file for file in changed_files if Path(file).suffix in source_suffixes)
    if files:
        subprocess.check_call([parsed.tool, "-i", "--", *files], cwd=project_dir)


def run_cleanup(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="yae cleanup", description="Re-sync submodules and delete ignored files")
    parser.add_argument("--project_dir", type=Path, default=Path.cwd(), help="Path to directory with your project")
    parsed = parser.parse_args(args)

    project_dir = parsed.project_dir.resolve()
    has_submodules = subprocess.run(
        ["git", "config", "--file", ".gitmodules", "--get-regexp", "path"],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0
    if has_submodules:
        subprocess.check_call(["git", "submodule", "deinit", "--force", "--all"], cwd=project_dir)
        subprocess.check_call(["git", "submodule", "sync", "--recursive"], cwd=project_dir)
        subprocess.check_call(["git", "submodule", "update", "--init", "--recursive"], cwd=project_dir)
    subprocess.check_call(["git", "clean", "-ffdX"], cwd=project_dir)


def main() -> None:
    yae_root = Path(__file__).resolve().parent.parent
    args = sys.argv[1:]

    if not args or args[0] in {"-h", "--help"}:
        print_help()
        return

    command = args[0]
    command_args = args[1:]
    if command == "configure":
        run_configure(yae_root, command_args)
        return
    if command == "build":
        run_build(yae_root, command_args)
        return
    if command == "run":
        run_app(yae_root, command_args)
        return
    if command == "format":
        run_format(command_args)
        return
    if command == "cleanup":
        run_cleanup(command_args)
        return

    print(f"Unknown yae command: {command}", file=sys.stderr)
    print_help()
    raise SystemExit(2)


if __name__ == "__main__":
    main()
