from __future__ import annotations

from pathlib import Path
from typing import Sequence
import subprocess

from yae.github_link import GITHUB_URL_PREFIX


def run_git(path: Path, args: Sequence[str]) -> str | None:
    """Runs a git command in `path` and returns its stripped stdout, or None if it fails."""
    try:
        return subprocess.check_output(
            ["git", "-C", path.as_posix(), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return None


def check_git(path: Path, args: Sequence[str]) -> bool:
    """Runs a git command in `path` and returns whether it succeeded."""
    try:
        subprocess.check_call(
            ["git", "-C", path.as_posix(), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def normalize_url(url: str) -> str:
    """Normalizes a git URL so equivalent SSH/HTTPS forms compare equal."""
    if url.startswith("git@github.com:"):
        url = GITHUB_URL_PREFIX + url.removeprefix("git@github.com:")
    return url.removesuffix(".git").rstrip("/")


def checkout_matches_ref(checkout_path: Path, ref: str) -> bool:
    """True if the checkout is on `ref` (as the current branch or with HEAD at the ref commit)."""
    current_branch = run_git(checkout_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if current_branch == ref:
        return True

    head_commit = run_git(checkout_path, ["rev-parse", "HEAD"])
    ref_commit = run_git(checkout_path, ["rev-list", "-n", "1", ref])
    return head_commit is not None and head_commit == ref_commit
