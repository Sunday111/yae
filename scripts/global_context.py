from pathlib import Path


class GlobalContext:
    """Global state of the script"""

    def __init__(self):
        self.__scripts_dir = Path(__file__).parent.resolve()
        self.__root_dir = self.__scripts_dir.parent.resolve()
        self.__modules_dir = (self.root_dir / "modules").resolve()
        self.__generated_dir = self.__root_dir / "generated"
        self.__cloned_modules_dir = self.__root_dir / "cloned_repositories"
        self.__cloned_modules_registry_file = self.__cloned_modules_dir / "registry.json"

    @property
    def root_dir(self) -> Path:
        """Returns path to the root directory"""
        return self.__root_dir

    @property
    def modules_dir(self) -> Path:
        """Returns path to the directory with modules"""
        return self.__modules_dir

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
