"""Locates and loads scripts that ship with yae-support.

Generated projects call these scripts without yae present, so they live in
yae-support rather than here. yae decides how they are called, so they are tested
here, which means the tests need to find the checkout.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

from yae.resolver import YAE_SUPPORT_PACKAGE_NAME

SUPPORT_ROOT_ENV = "YAE_SUPPORT_ROOT"


def find_support_root() -> Path:
    """Path to a yae-support checkout.

    YAE_SUPPORT_ROOT wins, so a test run can point at a specific checkout. Otherwise
    look next to the yae repository, which is how the repositories are laid out on a
    development machine.
    """

    from_env = os.environ.get(SUPPORT_ROOT_ENV)
    if from_env:
        support_root = Path(from_env)
        if not support_root.is_dir():
            raise RuntimeError(f"{SUPPORT_ROOT_ENV} points at a directory that does not exist: {support_root}")
        return support_root

    yae_root = Path(__file__).resolve().parents[3]
    candidates = [
        yae_root.parent / YAE_SUPPORT_PACKAGE_NAME,
        yae_root.parent / "yae_data" / "Sunday111" / YAE_SUPPORT_PACKAGE_NAME / "main",
        yae_root / ".cache" / "self-test-repositories" / "Sunday111" / YAE_SUPPORT_PACKAGE_NAME / "main",
    ]
    for candidate in candidates:
        if (candidate / "scripts").is_dir():
            return candidate

    searched = "\n  ".join(candidate.as_posix() for candidate in candidates)
    raise RuntimeError(
        f"Could not find a {YAE_SUPPORT_PACKAGE_NAME} checkout. "
        f"Set {SUPPORT_ROOT_ENV} to one. Searched:\n  {searched}"
    )


def load_support_script(name: str) -> ModuleType:
    """Imports a script from yae-support's scripts directory by name."""
    script_path = find_support_root() / "scripts" / f"{name}.py"
    if not script_path.is_file():
        raise RuntimeError(f"No such script in yae-support: {script_path}")

    spec = importlib.util.spec_from_file_location(f"yae_support_{name}", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_stage_directories() -> ModuleType:
    return load_support_script("stage_directories")
