from pathlib import Path

from yae.project_config import ProjectConfig
from yae.settings import ResolvedSettings


class GlobalContext:
    """Global state of the script"""

    def __init__(self, project_root: Path, cloned_repositories_dir: Path | None, show_clone_progress: bool = False):
        self.__settings = ResolvedSettings.from_project(project_root, cloned_repositories_dir)
        self.__project_config = ProjectConfig(self.__settings.project_root, self.__settings)
        self.__show_clone_progress = show_clone_progress

    @property
    def root_dir(self) -> Path:
        return self.project_root_dir

    @property
    def project_config(self) -> ProjectConfig:
        return self.__project_config

    @property
    def settings(self) -> ResolvedSettings:
        return self.__settings

    @property
    def project_root_dir(self) -> Path:
        """Returns root directory of the project that uses yae"""
        return self.__project_config.root_dir

    @property
    def show_clone_progress(self) -> bool:
        return self.__show_clone_progress
