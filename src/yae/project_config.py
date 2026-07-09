from pathlib import Path
from typing import Generator
import os

from yae import json_utils
from yae import yae_constants
from yae.github_link import GitHubLink
from yae.local_config import read_local_config
from yae.package import Package


DEFAULT_YAE_SUPPORT_LINK = "https://github.com/Sunday111/yae-support main"
EXTERNAL_MODULES_DIR_ENV = "YAE_EXTERNAL_MODULES_DIR"
LOCAL_CONFIG_EXTERNAL_MODULES_DIR_KEYS = ("external_modules_dir", "cloned_repositories_dir")


class ProjectConfig:
    def __init__(self, root_dir: Path, cloned_repositories_dir: Path | None):
        self.root_dir = root_dir
        self.config_file_path = root_dir / "yae_project.json"
        json = json_utils.read_json_file(self.config_file_path)
        self.name = json["name"]
        self.cpp_standard = json["cpp"]["standard"]
        self.enable_lto_globally: bool | None = json.get("enable_lto_globally", None)
        self.yae_support_link = self.__read_yae_support_link(json)
        self.cloned_repos_dir, self.cloned_repos_dir_source = self.__choose_cloned_repo_dir(cloned_repositories_dir)
        self.cloned_modules_registry_file: Path = self.cloned_repos_dir / "registry.json"
        self.__packages = list(self.__glob_local_packages())

    def __read_yae_support_link(self, json: dict) -> GitHubLink:
        yae_support = json.get("yae_support", {})
        if isinstance(yae_support, str):
            return GitHubLink.parse(yae_support)
        return GitHubLink.parse(yae_support.get("link", DEFAULT_YAE_SUPPORT_LINK))

    def __glob_local_packages(self) -> Generator[Package, None, None]:
        for path in Package.glob_files_in(self.root_dir):
            if (
                self.cloned_repos_dir.is_relative_to(self.root_dir)
                and path.is_relative_to(self.cloned_repos_dir)
            ):
                continue
            if path.is_relative_to(self.default_cloned_repositories_dir):
                continue
            yield Package(path)

    def __choose_cloned_repo_dir(self, cli_param: Path | None) -> tuple[Path, str]:
        external_modules_paths: list[tuple[Path, str]] = list()

        # Attempt to use property from CLI
        if cli_param is not None:
            external_modules_paths.append((cli_param, "cli property"))

        # Attempt to use property from local config
        if local_config_path := self.__read_local_external_modules_dir():
            external_modules_paths.append((local_config_path, "local config"))

        # Attempt to use property from environment
        if env_value := os.environ.get(EXTERNAL_MODULES_DIR_ENV):
            external_modules_paths.append((Path(env_value), "environment variable"))

        # Attempt to use property from json
        external_modules_paths.append((self.default_cloned_repositories_dir, "default"))

        if not external_modules_paths:
            raise RuntimeError("Path to external modules is not specified")

        return external_modules_paths[0]

    def __read_local_external_modules_dir(self) -> Path | None:
        local_config = read_local_config(self.root_dir)
        for key in LOCAL_CONFIG_EXTERNAL_MODULES_DIR_KEYS:
            if value := local_config.get(key):
                return self.__resolve_project_path(value)

        local_default_configuration = local_config.get("default_configuration", {})
        for key in LOCAL_CONFIG_EXTERNAL_MODULES_DIR_KEYS:
            if value := local_default_configuration.get(key):
                return self.__resolve_project_path(value)
        return None

    def __resolve_project_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.root_dir / path

    @property
    def default_cloned_repositories_dir(self) -> Path:
        return self.root_dir / yae_constants.CLONED_REPOSITORIES_DIRECTORY_NAME

    @property
    def packages(self) -> Generator[Package, None, None]:
        yield from self.__packages
