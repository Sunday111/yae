from __future__ import annotations

from pathlib import Path
import subprocess
import time

from yae import git
from yae.cloned_repository_registry import ClonedRepositoryRegistry
from yae.errors import FetchError
from yae.global_context import GlobalContext
from yae.yae_logging import get_logger


logger = get_logger(__name__)


class RepositoryFetcher:
    """Makes a `(url, tag)` available at a local path, cloning it if needed.

    Resolution asks the fetcher to `ensure` each dependency exists; the fetcher
    clones missing checkouts (or adopts a compatible existing one) and records
    the result in the registry. Keeping this separate from resolution makes the
    network side effect explicit and injectable.
    """

    def __init__(self, ctx: GlobalContext, registry: ClonedRepositoryRegistry):
        self.ctx = ctx
        self.registry = registry

    def ensure(self, path: Path, git_url: str, git_tag: str) -> bool:
        """Ensures `git_url`@`git_tag` is checked out at `path`. Returns success."""
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise FetchError("Repository checkout path must stay within the repositories root")
        repositories_root = self.ctx.project_config.cloned_repositories_dir.resolve()
        clone_destination = (repositories_root / path).resolve()
        if not clone_destination.is_relative_to(repositories_root):
            raise FetchError("Repository checkout path must stay within the repositories root")
        recorded = self.registry.get(path)
        if recorded is not None:
            existing_git_url, existing_git_tag = recorded
            if existing_git_url != git_url:
                logger.warning(
                    "Trying to register git repositories with different urls (%s and %s in the same local path %s)",
                    existing_git_url,
                    git_url,
                    path.as_posix(),
                )
                return False
            if existing_git_tag != git_tag:
                logger.warning(
                    "Trying to register git repositories with different tags (%s and %s in the same local path %s)",
                    existing_git_tag,
                    git_tag,
                    path.as_posix(),
                )
                return False
            return True

        if clone_destination.exists():
            return self.__register_existing_checkout(path, clone_destination, git_url, git_tag)

        return self.__clone(path, clone_destination, git_url, git_tag)

    def __clone(self, path: Path, clone_destination: Path, git_url: str, git_tag: str) -> bool:
        logger.info("Cloning %s (tag: %s)", git_url, git_tag)

        start_time = time.time()
        clone_destination.parent.mkdir(parents=True, exist_ok=True)
        clone_cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            git_tag,
            git_url,
            clone_destination.as_posix(),
        ]
        if self.ctx.show_clone_progress:
            clone_cmd.insert(2, "--progress")
        try:
            if self.ctx.show_clone_progress:
                subprocess.check_call(clone_cmd)
            else:
                subprocess.check_call(
                    clone_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except subprocess.CalledProcessError as err:
            raise FetchError(
                f"Failed to clone {git_url} (tag: {git_tag}): git exited with {err.returncode}"
            )
        logger.info("Cloned %s in %.2fs", git_url, time.time() - start_time)

        self.registry.record(path, git_url, git_tag)
        return True

    def __register_existing_checkout(self, path: Path, checkout_path: Path, git_url: str, git_tag: str) -> bool:
        remote_url = git.run_git(checkout_path, ["remote", "get-url", "origin"])
        if remote_url is None:
            logger.warning("Existing path is not a git checkout: %s", checkout_path.as_posix())
            return False

        if git.normalize_url(remote_url) != git.normalize_url(git_url):
            logger.warning(
                "Existing checkout has different origin (%s and %s in the same local path %s)",
                remote_url,
                git_url,
                path.as_posix(),
            )
            return False

        current_branch = git.run_git(checkout_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if current_branch == git_tag:
            self.registry.record(path, git_url, git_tag)
            return True

        head_commit = git.run_git(checkout_path, ["rev-parse", "HEAD"])
        tag_commit = git.run_git(checkout_path, ["rev-list", "-n", "1", git_tag])
        if head_commit is not None and head_commit == tag_commit:
            self.registry.record(path, git_url, git_tag)
            return True

        if tag_commit is not None and git.check_git(checkout_path, ["merge-base", "--is-ancestor", git_tag, "HEAD"]):
            self.registry.record(path, git_url, git_tag)
            return True

        logger.warning(
            "Existing checkout at %s is not on requested ref %s (current ref: %s)",
            checkout_path.as_posix(),
            git_tag,
            current_branch or "unknown",
        )
        return False
