import json_utils
from pathlib import Path


class ProjectConfig:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.config_file_path = root_dir / "yae_project.json"
        json = json_utils.read_json_file(self.config_file_path)
        self.name = json["name"]
        self.cpp_standard = json["cpp"]["standard"]
        self.modules_dir = self.root_dir / json["modules_dir"]
