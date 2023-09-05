import subprocess

from yae import *


class ClonedRepoRegistry:
    def __init__(self, ctx: GlobalContext):
        self.cloned_repos: dict[Path, tuple[str, str]] = dict()
        self.ctx = ctx

        self.__read_registry_file()

    def fetch_repo(self, path: Path, git_url: str, git_tag: str) -> bool:
        if path in self.cloned_repos:
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
        subprocess.check_call(
            ["git", "clone", "--depth", "1", "--branch", git_tag, git_url, self.ctx.cloned_modules_dir / path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # if clone happens without problems, dump registry to disk
        self.__save_registry_file()

        return True

    def __save_registry_file(self):
        converted = {
            key.as_posix(): {
                "GitUrl": value[0],
                "GitTag": value[1],
            }
            for key, value in self.cloned_repos.items()
        }
        save_json_to_file(self.ctx.cloned_modules_registry_file, converted)

    def __read_registry_file(self):
        if self.ctx.cloned_modules_registry_file.exists():
            for path_str, identifier in read_json_file(self.ctx.cloned_modules_registry_file).items():
                self.cloned_repos[Path(path_str)] = identifier["GitUrl"], identifier["GitTag"]
