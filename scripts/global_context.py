from pathlib import Path
from typing import Generator
from project_config import ProjectConfig


class GlobalContext:
    """Global state of the script"""

    def __init__(self, project_root: Path, external_modules_dir: Path | None):
        self.__scripts_dir = Path(__file__).parent.resolve()
        self.__yae_root_dir = self.__scripts_dir.parent.resolve()
        self.__project_config = ProjectConfig(project_root, external_modules_dir)
        self.__yae_modules_dir = (self.__yae_root_dir / "modules").resolve()
        self.__generated_dir = self.__yae_root_dir / "generated"

    @property
    def root_dir(self) -> Path:
        if self.project_root_dir is None:
            return self.yae_root_dir
        return self.project_root_dir

    @property
    def yae_root_dir(self) -> Path:
        """Returns path to the root directory of yae project"""
        return self.__yae_root_dir

    @property
    def project_config(self) -> ProjectConfig:
        return self.__project_config

    @property
    def project_root_dir(self) -> Path:
        """Returns root directory of the project that uses yae"""
        return self.__project_config.root_dir

    @property
    def yae_modules_dir(self) -> Path:
        """Returns path to the directory with modules"""
        return self.__yae_modules_dir

    @property
    def scripts_dir(self) -> Path:
        """Returns path to the directory with scripts"""
        return self.__scripts_dir

    @property
    def generated_dir(self) -> Path:
        """Returns path to the directorty with generated files (CMakeLists, etc)"""
        return self.__generated_dir
