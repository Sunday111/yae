from pathlib import Path
from typing import Generator


class GlobalContext:
    """Global state of the script"""

    def __init__(self, project_root: Path = None):
        self.__scripts_dir = Path(__file__).parent.resolve()
        self.__yae_root_dir = self.__scripts_dir.parent.resolve()
        self.__yae_modules_dir = (self.__yae_root_dir / "modules").resolve()
        self.__generated_dir = self.__yae_root_dir / "generated"
        self.__cloned_modules_dir = self.__yae_root_dir / "cloned_repositories"
        self.__cloned_modules_registry_file = self.__cloned_modules_dir / "registry.json"
        self.__project_root = project_root
        if project_root is None:
            self.__project_modules_dir = None
        else:
            self.__project_modules_dir = self.__project_root / "modules"

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
    def project_root_dir(self) -> Path | None:
        """Returns root directory of the project that uses yae"""
        return self.__project_root

    @property
    def yae_modules_dir(self) -> Path:
        """Returns path to the directory with modules"""
        return self.__yae_modules_dir

    @property
    def all_modules_dirs(self) -> Generator[Path, None, None]:
        yield self.yae_modules_dir
        if not (self.project_modules_dir is None):
            yield self.project_modules_dir

    @property
    def project_modules_dir(self) -> Path | None:
        """Returns path to the directory with project modules. Or none if yae is being used by itself"""
        return self.__project_modules_dir

    @property
    def scripts_dir(self) -> Path:
        """Returns path to the directory with scripts"""
        return self.__scripts_dir

    @property
    def generated_dir(self) -> Path:
        """Returns path to the directorty with generated files (CMakeLists, etc)"""
        return self.__generated_dir

    @property
    def cloned_modules_dir(self) -> Path:
        return self.__cloned_modules_dir

    @property
    def cloned_modules_registry_file(self) -> Path:
        return self.__cloned_modules_registry_file
