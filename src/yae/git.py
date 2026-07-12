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


def status_short(path: Path) -> list[str] | None:
    """Returns the `git status --porcelain` lines for `path` (empty list if clean),
    or None if `path` is not a git work tree."""
    output = run_git(path, ["status", "--porcelain"])
    if output is None:
        return None
    return [line for line in output.splitlines() if line]


def has_remotes(path: Path) -> bool:
    """Whether the repository has any remotes configured."""
    return bool(run_git(path, ["remote"]))


def current_branch(path: Path) -> str | None:
    """Returns the current branch name, or None when HEAD is detached
    or `path` is not a git work tree."""
    output = run_git(path, ["symbolic-ref", "--short", "-q", "HEAD"])
    return output or None


def unpushed_commit_count(path: Path) -> int | None:
    """Returns the number of commits on HEAD that its upstream branch does not have,
    or None when there is no upstream to compare against."""
    output = run_git(path, ["rev-list", "--count", "@{upstream}..HEAD"])
    if output is None:
        return None
    return int(output)


def checkout_matches_ref(checkout_path: Path, ref: str) -> bool:
    """True if the checkout is on `ref` (as the current branch or with HEAD at the ref commit)."""
    current_branch = run_git(checkout_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if current_branch == ref:
        return True

    head_commit = run_git(checkout_path, ["rev-parse", "HEAD"])
    ref_commit = run_git(checkout_path, ["rev-list", "-n", "1", ref])
    return head_commit is not None and head_commit == ref_commit
