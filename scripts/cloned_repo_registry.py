import subprocess
from pathlib import Path

import json_utils
from global_context import GlobalContext
import time


class ClonedRepoRegistry:
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

        self.cloned_repos[path] = git_url, git_tag
        print(f"Cloning {git_url}")
        print(f"    url: {git_url}")
        print(f"    tag: {git_tag}")

        start_time = time.time()
        clone_cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            git_tag,
            git_url,
            (self.ctx.project_config.cloned_repos_dir / path).as_posix(),
        ]
        try:
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

    def exists(self, path: Path) -> bool:
        return path in self.cloned_repos

    def exists_and_same_ref(self, path: Path, git_url: str, git_tag: str) -> bool:
        if self.exists(path):
            existing_git_url, existing_git_tag = self.cloned_repos[path]
            return existing_git_tag == git_tag and existing_git_url == git_url

        return False

    def __save_registry_file(self):
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
                self.cloned_repos[Path(path_str)] = identifier["GitUrl"], identifier["GitTag"]
