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

from yae.github_link import GitHubLink
from yae.project_config import DEFAULT_YAE_SUPPORT_LINK
from yae.resolver import YAE_SUPPORT_PACKAGE_NAME
from yae.settings import CLONED_REPOSITORIES_DIR_ENV

SUPPORT_ROOT_ENV = "YAE_SUPPORT_ROOT"


def _candidate_roots() -> list[Path]:
    yae_root = Path(__file__).resolve().parents[3]
    # Wherever it ends up, the checkout is laid out the way yae lays every checkout out.
    checkout_subdir = GitHubLink.parse(DEFAULT_YAE_SUPPORT_LINK).subdir

    candidates = [yae_root.parent / YAE_SUPPORT_PACKAGE_NAME]

    cloned_repositories_dir = os.environ.get(CLONED_REPOSITORIES_DIR_ENV)
    if cloned_repositories_dir:
        candidates.append(Path(cloned_repositories_dir) / checkout_subdir)

    # Whatever a previous self-test run fetched.
    candidates.append(yae_root / ".cache" / "self-test-repositories" / checkout_subdir)

    return candidates


def find_support_root() -> Path:
    """Path to a yae-support checkout.

    YAE_SUPPORT_ROOT wins, so a test run - CI, for one - can name the checkout outright.
    Otherwise look where a checkout plausibly is: beside the yae repository, under the
    cloned repositories directory, or in what a self-test run fetched.
    """

    from_env = os.environ.get(SUPPORT_ROOT_ENV)
    if from_env:
        support_root = Path(from_env)
        if not support_root.is_dir():
            raise RuntimeError(f"{SUPPORT_ROOT_ENV} points at a directory that does not exist: {support_root}")
        return support_root

    candidates = _candidate_roots()
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
