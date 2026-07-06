from pathlib import Path

from yae.project_config import ProjectConfig


class GlobalContext:
    """Global state of the script"""

    def __init__(self, project_root: Path, external_modules_dir: Path | None):
        self.__project_config = ProjectConfig(project_root, external_modules_dir)

    @property
    def root_dir(self) -> Path:
        return self.project_root_dir

    @property
    def project_config(self) -> ProjectConfig:
        return self.__project_config

    @property
    def project_root_dir(self) -> Path:
        """Returns root directory of the project that uses yae"""
        return self.__project_config.root_dir
