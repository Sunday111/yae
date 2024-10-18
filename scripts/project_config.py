import json_utils
from pathlib import Path
import yae_package
from typing import Generator


class ProjectConfig:
    def __init__(self, root_dir: Path, cloned_repositories_dir: Path | None):
        self.root_dir = root_dir
        self.config_file_path = root_dir / "yae_project.json"
        json = json_utils.read_json_file(self.config_file_path)
        self.name = json["name"]
        self.cpp_standard = json["cpp"]["standard"]
        self.enable_lto_globally: bool | None = json.get("enable_lto_globally", None)
        self.cloned_repos_dir: Path = self.__choose_cloned_repo_dir(
            json.get("cloned_dependencies_dir"), cloned_repositories_dir
        )
        self.cloned_modules_registry_file: Path = self.cloned_repos_dir / "registry.json"
        self.__packages = list(
            map(
                yae_package.Package,
                filter(lambda x: not x.is_relative_to(root_dir), yae_package.Package.glob_files_in(root_dir)),
            )
        )

    def __choose_cloned_repo_dir(self, json_param: str | None, cli_param: Path | None) -> Path:
        external_modules_paths: list[tuple[Path, str]] = list()

        # Attempt to use property from CLI
        if cli_param is not None:
            external_modules_paths.append((cli_param, "cli property"))

        # Attempt to use property from json
        if json_param is not None:
            external_modules_paths.append((self.root_dir / json_param, "from project file"))

        if not external_modules_paths:
            raise RuntimeError("Path to external modules is not specified")

        return external_modules_paths[0][0]

    @property
    def packages(self) -> Generator[yae_package.Package, None, None]:
        yield from self.__packages
