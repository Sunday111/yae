import subprocess
from pathlib import Path
from typing import Sequence

from yae import json_utils
from yae.global_context import GlobalContext
import time


def _run_git(path: Path, args: Sequence[str]) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", path.as_posix(), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return None


def _check_git(path: Path, args: Sequence[str]) -> bool:
    try:
        subprocess.check_call(
            ["git", "-C", path.as_posix(), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _normalize_git_url(url: str) -> str:
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url.removeprefix("git@github.com:")
    return url.removesuffix(".git").rstrip("/")


class ClonedRepositoryRegistry:
    def __init__(self, ctx: GlobalContext):
        self.cloned_repos: dict[Path, tuple[str, str]] = dict()
        self.ctx = ctx

        self.__read_registry_file()

    def fetch_repo(self, path: Path, git_url: str, git_tag: str) -> bool:
        if self.exists(path):
            existing_git_url, existing_git_tag = self.cloned_repos[path]
            if existing_git_url != git_url:
                print(
                    f"Trying to register git repositories with different urls ({existing_git_url} and {git_url} in the same local path {path.as_posix()})"
                )
                return False
            if existing_git_tag != git_tag:
                print(
                    f"Trying to register git repositories with different tags ({existing_git_tag} and {git_tag} in the same local path {path.as_posix()})"
                )
                return False
            return True

        clone_destination = self.ctx.project_config.cloned_repos_dir / path
        if clone_destination.exists():
            if self.__try_register_existing_checkout(path, clone_destination, git_url, git_tag):
                return True
            return False

        self.cloned_repos[path] = git_url, git_tag
        print(f"Cloning {git_url}", flush=True)
        print(f"    url: {git_url}", flush=True)
        print(f"    tag: {git_tag}", flush=True)

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
            print(f'Failed to clone repository. Command: {" ".join(err.cmd)}. Return code: {err.returncode}')
            raise
        print(f"    time: {time.time() - start_time:.2f}s")

        # if clone happens without problems, dump registry to disk
        self.__save_registry_file()

        return True

    def __try_register_existing_checkout(self, path: Path, checkout_path: Path, git_url: str, git_tag: str) -> bool:
        remote_url = _run_git(checkout_path, ["remote", "get-url", "origin"])
        if remote_url is None:
            print(f"Existing path is not a git checkout: {checkout_path.as_posix()}")
            return False

        if _normalize_git_url(remote_url) != _normalize_git_url(git_url):
            print(
                f"Existing checkout has different origin ({remote_url} and {git_url} in the same local path {path.as_posix()})"
            )
            return False

        current_branch = _run_git(checkout_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if current_branch == git_tag:
            self.cloned_repos[path] = git_url, git_tag
            self.__save_registry_file()
            return True

        head_commit = _run_git(checkout_path, ["rev-parse", "HEAD"])
        tag_commit = _run_git(checkout_path, ["rev-list", "-n", "1", git_tag])
        if head_commit is not None and head_commit == tag_commit:
            self.cloned_repos[path] = git_url, git_tag
            self.__save_registry_file()
            return True

        if tag_commit is not None and _check_git(checkout_path, ["merge-base", "--is-ancestor", git_tag, "HEAD"]):
            self.cloned_repos[path] = git_url, git_tag
            self.__save_registry_file()
            return True

        print(
            f"Existing checkout at {checkout_path.as_posix()} is not on requested ref {git_tag} "
            f"(current ref: {current_branch or 'unknown'})"
        )
        return False

    def exists(self, path: Path) -> bool:
        return path in self.cloned_repos

    def exists_and_same_ref(self, path: Path, git_url: str, git_tag: str) -> bool:
        if self.exists(path):
            existing_git_url, existing_git_tag = self.cloned_repos[path]
            return existing_git_tag == git_tag and existing_git_url == git_url

        return False

    def __save_registry_file(self):
        self.ctx.project_config.cloned_modules_registry_file.parent.mkdir(parents=True, exist_ok=True)
        converted = {
            key.as_posix(): {
                "GitUrl": value[0],
                "GitTag": value[1],
            }
            for key, value in self.cloned_repos.items()
        }
        json_utils.save_json_to_file(self.ctx.project_config.cloned_modules_registry_file, converted)

    def __read_registry_file(self):
        if self.ctx.project_config.cloned_modules_registry_file.exists():
            for path_str, identifier in json_utils.read_json_file(
                self.ctx.project_config.cloned_modules_registry_file
            ).items():
                if (self.ctx.project_config.cloned_repos_dir / str(path_str)).exists():
                    self.cloned_repos[Path(path_str)] = identifier["GitUrl"], identifier["GitTag"]
