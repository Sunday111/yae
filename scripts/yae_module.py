from typing import Iterable, Callable, Generator
import enum
from pathlib import Path
from global_context import GlobalContext

import json_utils

CPP_SUFFIXES = [".cpp"]
HPP_SUFFIXES = [".hpp"]


class ModuleType(enum.Enum):
    """The type of module"""

    LIBRARY = 1
    EXECUTABLE = 2
    GITCLONE = 3


class Module:
    """Represents .module.json file"""

    def __init__(self, file_path: Path):
        self.__module_file_path = file_path
        self.__module_root_dir = self.__module_file_path.parent.resolve()
        self.__module_name = file_path.stem.replace(".module", "")
        self.__private_modules: list[str] = list()
        self.__public_modules: list[str] = list()
        self.__module_type = ModuleType.LIBRARY
        json: dict = json_utils.read_json_file(file_path)
        self.__read_module_type(json)
        self.__read_dependencies(json)
        if self.module_type == ModuleType.GITCLONE:
            self.__git_url = json["GitUrl"]
            self.__git_tag = json["GitTag"]

        self.__cmake_target_name: None | str = json.get("TargetName", None)
        self.__enable_testing: bool = json.get("EnableTesting", False)
        self.__cmake_options: dict[str, bool | int | str] = json.get("CMakeOptions", {})
        self.__enable_lto: bool | None = json.get("EnableLTO", None)

        if self.module_type == ModuleType.GITCLONE:
            self.__local_path = Path(json["LocalPath"])

        self.__post_build_copy_dirs: list[Path] = [
            self.root_dir / x for x in json.get("CopyDirectoriesAfterBuild", list())
        ]

    def __read_dependencies(self, file_data: dict):
        key_dependencies = "Dependencies"
        key_public = "Public"
        key_private = "Private"
        dependedncies: dict = file_data.get(key_dependencies, {})
        self.__private_modules = dependedncies.get(key_private, dict())
        self.__public_modules = dependedncies.get(key_public, dict())

    def __read_module_type(self, file_data: dict):
        key_module_type = "ModuleType"
        module_type_str: str = file_data[key_module_type]
        self.__module_type = ModuleType[module_type_str.upper()]

    @property
    def post_build_copy_dirs(self) -> Generator[Path, None, None]:
        yield from self.__post_build_copy_dirs

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
            return (ctx.project_config.cloned_modules_dir / self.local_path).relative_to(ctx.root_dir)
        return self.root_dir.relative_to(ctx.root_dir)

    @property
    def cmake_target_name(self) -> str:
        if self.__cmake_target_name is None:
            return self.name
        return self.__cmake_target_name

    @property
    def enable_testing(self) -> bool:
        return self.__enable_testing

    @property
    def cmake_options(self) -> dict[str, int | str | bool]:
        return self.__cmake_options

    @property
    def local_path(self) -> Path:
        return self.__local_path

    @property
    def enable_lto(self) -> bool | None:
        return self.__enable_lto

    @property
    def specifies_lto(self) -> bool:
        return not (self.enable_lto is None)
