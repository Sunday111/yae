from __future__ import annotations

from pathlib import Path
from typing import Generator

from yae import json_utils
from yae import yae_constants
from yae.errors import ProjectError
from yae.github_link import GitHubLink
from yae.package import Package
from yae.settings import ResolvedSettings


DEFAULT_YAE_SUPPORT_LINK = "https://github.com/Sunday111/yae-support main"
CXXLIB_REQUIREMENTS = ("llvm-static", "gcc-static")


class ProjectConfig:
    def __init__(self, root_dir: Path, settings: ResolvedSettings):
        self.root_dir = root_dir
        self.settings = settings
        self.config_file_path = root_dir / yae_constants.PROJECT_CONFIG_FILE_NAME
        json = json_utils.read_json_file(self.config_file_path)
        self.name = json["name"]
        self.cpp_standard = json["cpp"]["standard"]
        self.required_cxxlib: str | None = json.get("require_cxxlib")
        if self.required_cxxlib is not None and self.required_cxxlib not in CXXLIB_REQUIREMENTS:
            expected = ", ".join(CXXLIB_REQUIREMENTS)
            raise ProjectError(f"Unknown require_cxxlib '{self.required_cxxlib}'. Expected one of: {expected}")
        self.enable_lto_globally: bool | None = json.get("enable_lto_globally", None)
        self.yae_support_link = self.__read_yae_support_link(json)
        self.__packages = list(self.__glob_local_packages())

    def __read_yae_support_link(self, json: dict) -> GitHubLink:
        yae_support = json.get("yae_support", {})
        if isinstance(yae_support, str):
            return GitHubLink.parse(yae_support)
        return GitHubLink.parse(yae_support.get("link", DEFAULT_YAE_SUPPORT_LINK))

    def __glob_local_packages(self) -> Generator[Package, None, None]:
        for path in Package.glob_files_in(self.root_dir):
            if (
                self.cloned_repositories_dir.is_relative_to(self.root_dir)
                and path.is_relative_to(self.cloned_repositories_dir)
            ):
                continue
            if path.is_relative_to(self.default_cloned_repositories_dir):
                continue
            yield Package(path)

    @property
    def default_cloned_repositories_dir(self) -> Path:
        return self.settings.default_cloned_repositories_dir

    @property
    def cloned_repositories_dir(self) -> Path:
        return self.settings.cloned_repositories_dir

    @property
    def cloned_repositories_registry_file(self) -> Path:
        return self.settings.registry_file

    @property
    def packages(self) -> Generator[Package, None, None]:
        yield from self.__packages
