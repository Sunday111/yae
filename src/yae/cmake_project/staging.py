from __future__ import annotations

from pathlib import Path

from yae.module import Module


def copy_target_name(module: Module) -> str:
    return f"{module.cmake_target_name}_copy_files"


def copy_directories_by_destination(module: Module) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for copy_dir in sorted(module.post_build_copy_dirs):
        result.setdefault(copy_dir.stem, []).append(copy_dir)
    return result


def staging_manifest_relative_path(module: Module, destination: str) -> Path:
    return Path(destination) / f"{copy_target_name(module)}.manifest"
