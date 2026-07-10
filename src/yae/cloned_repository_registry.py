from __future__ import annotations

from pathlib import Path

from yae import json_utils
from yae.global_context import GlobalContext


class ClonedRepositoryRegistry:
    """Bookkeeping for cloned repository checkouts.

    Tracks which `(url, tag)` lives at which local path and persists that to
    `registry.json`. Fetching (cloning / adopting existing checkouts) lives in
    RepositoryFetcher; this class only records the outcome.
    """

    def __init__(self, ctx: GlobalContext):
        self.cloned_repos: dict[Path, tuple[str, str]] = dict()
        self.ctx = ctx

        self.__read_registry_file()

    def exists(self, path: Path) -> bool:
        return path in self.cloned_repos

    def get(self, path: Path) -> tuple[str, str] | None:
        return self.cloned_repos.get(path)

    def record(self, path: Path, git_url: str, git_tag: str) -> None:
        self.cloned_repos[path] = (git_url, git_tag)
        self.__save_registry_file()

    def exists_and_same_ref(self, path: Path, git_url: str, git_tag: str) -> bool:
        existing = self.get(path)
        return existing is not None and existing == (git_url, git_tag)

    def __save_registry_file(self):
        self.ctx.project_config.cloned_repositories_registry_file.parent.mkdir(parents=True, exist_ok=True)
        converted = {
            key.as_posix(): {
                "GitUrl": value[0],
                "GitTag": value[1],
            }
            for key, value in self.cloned_repos.items()
        }
        json_utils.save_json_to_file(self.ctx.project_config.cloned_repositories_registry_file, converted)

    def __read_registry_file(self):
        if self.ctx.project_config.cloned_repositories_registry_file.exists():
            for path_str, identifier in json_utils.read_json_file(
                self.ctx.project_config.cloned_repositories_registry_file
            ).items():
                if (self.ctx.project_config.cloned_repositories_dir / str(path_str)).exists():
                    self.cloned_repos[Path(path_str)] = identifier["GitUrl"], identifier["GitTag"]
