from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import time

from yae import git
from yae.commands.base import Command
from yae.commands.base import CommandContext
from yae.commands.base import add_cloned_repositories_dir_argument
from yae.errors import FetchError
from yae.errors import ProjectError
from yae.github_link import GITHUB_URL_PREFIX
from yae.github_link import parse_repo_path_from_url
from yae.settings import ResolvedSettings
from yae.yae_logging import get_logger


logger = get_logger(__name__)


def clone_github_project(
    url: str,
    ref: str,
    cloned_repositories_dir: Path,
    *,
    show_clone_progress: bool,
) -> Path:
    repo_path = parse_repo_path_from_url(url)
    if repo_path is None:
        raise ProjectError(f"Expected a GitHub URL like {GITHUB_URL_PREFIX}owner/repository")

    clone_destination = cloned_repositories_dir / repo_path
    if clone_destination.exists():
        remote_url = git.run_git(clone_destination, ["remote", "get-url", "origin"])
        if remote_url is None:
            raise FetchError(f"Existing path is not a git checkout: {clone_destination}")
        if git.normalize_url(remote_url) != git.normalize_url(url):
            raise FetchError(f"Existing checkout at {clone_destination} has origin {remote_url}, expected {url}")
        if not git.checkout_matches_ref(clone_destination, ref):
            raise FetchError(f"Existing checkout at {clone_destination} is not on requested ref {ref}")
        logger.info("Already cloned: %s", clone_destination)
        print(clone_destination)
        return clone_destination

    clone_destination.parent.mkdir(parents=True, exist_ok=True)
    clone_command = [
        "git",
        "clone",
        "--branch",
        ref,
        url,
        clone_destination.as_posix(),
    ]
    if show_clone_progress:
        clone_command.insert(2, "--progress")

    logger.info("Cloning %s (ref: %s) into %s", url, ref, clone_destination)
    start_time = time.time()
    try:
        if show_clone_progress:
            subprocess.check_call(clone_command)
        else:
            subprocess.check_call(clone_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as error:
        raise FetchError(f"Failed to clone {url} (ref: {ref}): git exited with {error.returncode}")
    logger.info("Cloned in %.2fs", time.time() - start_time)
    print(clone_destination)
    return clone_destination


class CloneCommand(Command):
    name = "clone"
    help = "Clone a GitHub project into the configured cloned repositories directory"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        add_cloned_repositories_dir_argument(parser)
        parser.add_argument("url", help="GitHub repository URL to clone")
        parser.add_argument("ref", nargs="?", default="main", help="Branch or tag to clone")

    def run(self, context: CommandContext, args: argparse.Namespace) -> None:
        settings = ResolvedSettings.from_project(Path.cwd(), context.cloned_repositories_dir_override)
        clone_github_project(
            args.url,
            args.ref,
            settings.cloned_repositories_dir,
            show_clone_progress=context.show_clone_progress,
        )
