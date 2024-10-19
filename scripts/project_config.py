import json_utils
from pathlib import Path
from yae_package import Package
from typing import Generator
import yae_constants


class ProjectConfig:
    def __init__(self, root_dir: Path, cloned_repositories_dir: Path | None):
        self.root_dir = root_dir
        self.config_file_path = root_dir / "yae_project.json"
        json = json_utils.read_json_file(self.config_file_path)
        self.name = json["name"]
        self.cpp_standard = json["cpp"]["standard"]
        self.enable_lto_globally: bool | None = json.get("enable_lto_globally", None)
        self.cloned_repos_dir: Path = self.__choose_cloned_repo_dir(cloned_repositories_dir)
        self.cloned_modules_registry_file: Path = self.cloned_repos_dir / "registry.json"
        self.__packages = list(self.__glob_local_packages())

    def __glob_local_packages(self) -> Generator[Package, None, None]:
        for path in Package.glob_files_in(self.root_dir):
            if path.is_relative_to(self.cloned_repos_dir):
                continue
            if path.is_relative_to(self.default_cloned_repositories_dir):
                continue
            yield Package(path)

    def __choose_cloned_repo_dir(self, cli_param: Path | None) -> Path:
        external_modules_paths: list[tuple[Path, str]] = list()

        # Attempt to use property from CLI
        if cli_param is not None:
            external_modules_paths.append((cli_param, "cli property"))

        # Attempt to use property from json
        external_modules_paths.append((self.default_cloned_repositories_dir, "default"))

        if not external_modules_paths:
            raise RuntimeError("Path to external modules is not specified")

        return external_modules_paths[0][0]

    @property
    def default_cloned_repositories_dir(self) -> Path:
        return self.root_dir / yae_constants.CLONED_REPOSITORIES_DIRECTORY_NAME

    @property
    def packages(self) -> Generator[Package, None, None]:
        yield from self.__packages
