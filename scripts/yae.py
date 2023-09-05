from pathlib import Path
import json
from typing import Iterable, Callable, Generator
import enum
import collections
import subprocess

CPP_SUFFIXES = [".cpp"]
HPP_SUFFIXES = [".hpp"]


class ModuleType(enum.Enum):
    """The type of module"""

    LIBRARY = 1
    EXECUTABLE = 2
    GITCLONE = 3


class GlobalContext:
    """Global state of the script"""

    def __init__(self):
        self.__scripts_dir = Path(__file__).parent.resolve()
        self.__root_dir = self.__scripts_dir.parent.resolve()
        self.__modules_dir = (self.root_dir / "modules").resolve()
        self.__generated_dir = self.__root_dir / "generated"
        self.__cloned_modules_dir = self.__root_dir / "cloned_repositories"

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


def read_json_file(path: Path) -> dict:
    with open(path, mode="r", encoding="utf-8") as file:
        return json.load(file)


class Module:
    """Represents .module.json file"""

    def __init__(self, file_path: Path):
        self.__module_file_path = file_path
        self.__module_root_dir = self.__module_file_path.parent.resolve()
        self.__module_name = self.root_dir.parts[-1]
        self.__private_modules: list[str] = list()
        self.__public_modules: list[str] = list()
        self.__module_type = ModuleType.LIBRARY
        file_data: dict = read_json_file(file_path)
        self.__read_module_type(file_data)
        self.__read_dependencies(file_data)
        if self.module_type == ModuleType.GITCLONE:
            self.__git_url = file_data["GitUrl"]
            self.__git_tag = file_data["GitTag"]

        self.__cmake_target_name: None | str = file_data.get("TargetName", None)
        self.__enable_testing: bool = file_data.get("EnableTesting", False)

    def __read_dependencies(self, file_data: dict):
        key_dependencies = "Dependencies"
        key_public = "Public"
        key_private = "Private"
        self.__private_modules = file_data[key_dependencies][key_private]
        self.__public_modules = file_data[key_dependencies][key_public]

    def __read_module_type(self, file_data: dict):
        key_module_type = "ModuleType"
        module_type_str: str = file_data[key_module_type]
        self.__module_type = ModuleType[module_type_str.upper()]

    @property
    def git_url(self) -> str:
        return self.__git_url

    @property
    def git_tag(self) -> str:
        return self.__git_tag

    @property
    def root_dir(self) -> Path:
        """Root directory of module"""
        return self.__module_root_dir

    @property
    def name(self) -> Path:
        """Module name"""
        return self.__module_name

    @property
    def module_file_path(self) -> Path:
        """Path to module.json file"""
        return self.__module_file_path

    @property
    def public_dependencies(self) -> list[str]:
        """Returns list of public dependencies for this modules"""
        return self.__public_modules

    @property
    def private_dependencies(self) -> list[str]:
        """Returns list of private dependencies for this modules"""
        return self.__private_modules

    @property
    def all_depepndencies(self) -> Generator[str, None, None]:
        """Yields all dependencis for this module"""
        yield from self.public_dependencies
        yield from self.private_dependencies

    @property
    def module_type(self) -> ModuleType:
        """Returns the type of module"""
        return self.__module_type

    @property
    def source_files(self) -> Iterable[Path]:
        """Yields all source files for module"""

        def suffixes() -> Iterable[str]:
            yield from CPP_SUFFIXES
            yield from HPP_SUFFIXES

        for suffix in suffixes():
            yield from self.root_dir.rglob(f"*{suffix}")

    def cmake_subdirectory(self, ctx: GlobalContext) -> Path:
        if self.module_type == ModuleType.GITCLONE:
            return self.rel_cloned_repo_path(ctx)
        return self.root_dir.relative_to(ctx.root_dir)

    def rel_cloned_repo_path(self, ctx: GlobalContext) -> Path:
        absolute = ctx.cloned_modules_dir / self.name
        relative = absolute.relative_to(ctx.root_dir)
        return relative

    @property
    def cmake_target_name(self) -> str:
        if self.__cmake_target_name is None:
            return self.name
        return self.__cmake_target_name

    @property
    def enable_testing(self) -> bool:
        return self.__enable_testing
