import json_utils
from pathlib import Path


class ProjectConfig:
    def __init__(self, root_dir: Path, cloned_repositories_dir: Path | None):
        self.root_dir = root_dir
        self.config_file_path = root_dir / "yae_project.json"
        json = json_utils.read_json_file(self.config_file_path)
        self.name = json["name"]
        self.cpp_standard = json["cpp"]["standard"]
        self.modules_dir = self.root_dir / json["modules_dir"]
        self.enable_lto_globally: bool | None = json.get("enable_lto_globally", None)

        external_modules_paths: list[tuple[Path, str]] = list()

        # Attempt to use property from CLI
        if cloned_repositories_dir is not None:
            external_modules_paths.append((cloned_repositories_dir, "cli property"))

        # Attempt to use property from json
        key_cloned_dependencies_dir = "cloned_dependencies_dir"
        if key_cloned_dependencies_dir in json:
            external_modules_paths.append((self.root_dir / json[key_cloned_dependencies_dir], "from project file"))

        if not external_modules_paths:
            raise RuntimeError("Path to external modules is not specified")

        self.cloned_repos_dir: Path = external_modules_paths[0][0]
        self.cloned_modules_registry_file: Path = self.cloned_repos_dir / "registry.json"
