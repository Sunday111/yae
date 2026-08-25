from __future__ import annotations

from typing import Iterable, Generator
from dataclasses import dataclass
import enum
from pathlib import Path

from yae import json_utils
from yae import yae_constants
from yae.errors import ModuleGraphError
from yae.github_link import parse_repo_path_from_url
from yae.github_link import versioned_repo_path

CPP_SUFFIXES = [".cpp"]
HPP_SUFFIXES = [".hpp"]
CUDA_SUFFIXES = [".cu"]


@dataclass(frozen=True)
class BinaryArtifact:
    """A prebuilt archive for one system triple, pinned by URL and checksum."""

    url: str
    sha256: str


class ModuleType(enum.Enum):
    """The type of module"""

    LIBRARY = 1
    EXECUTABLE = 2
    GITCLONE = 3
    # A prebuilt binary dependency: yae downloads and unpacks a released archive
    # for the host triple instead of cloning and building source, then exposes the
    # archive's own CMake package. See BINARY handling in the resolver and emitter.
    BINARY = 4


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
        if self.module_type == ModuleType.BINARY:
            self.__read_binary(json)
        self.__cmake_file_path = json.get("CMakeFilePath", "")

        self.__cmake_target_name: None | str = json.get("TargetName", None)
        self.__enable_testing: bool = json.get("EnableTesting", False)
        self.__cmake_options: dict[str, bool | int | str] = json.get("CMakeOptions", {})
        self.__cmake_modular_targets = json.get("CMakeModularTargets", list())
        self.__cmake_exclude_from_all = json.get("CMakeExcludeFromAll", False)
        self.__cmake_add_subdirectory = json.get("CMakeAddSubdirectory", True)
        self.__generate_cmake_file = json.get("GenerateCMakeFile", True)
        self.__enable_lto: bool | None = json.get("EnableLTO", None)
        self.__compress_debug_info: bool = json.get("CompressDebugInfo", True)
        self.__extra_cmake_files: list[str] = json.get("ExtraCMakeFiles", [])

        if self.module_type == ModuleType.GITCLONE:
            self.__local_path = self.__read_clone_local_path(json)

        self.__post_build_copy_dirs: list[Path] = [
            self.root_dir / x for x in json.get("CopyDirectoriesAfterBuild", list())
        ]

    def __read_dependencies(self, file_data: dict):
        key_dependencies = "Dependencies"
        key_public = "Public"
        key_private = "Private"
        dependencies: dict = file_data.get(key_dependencies, {})
        self.__private_modules = dependencies.get(key_private, dict())
        self.__public_modules = dependencies.get(key_public, dict())

    def __read_module_type(self, file_data: dict):
        key_module_type = "ModuleType"
        module_type_str: str = file_data[key_module_type]
        self.__module_type = ModuleType[module_type_str.upper()]

    def __read_clone_local_path(self, file_data: dict) -> Path:
        repo_path = parse_repo_path_from_url(self.git_url)
        if repo_path is not None:
            return versioned_repo_path(repo_path, self.git_tag)
        return Path(file_data["LocalPath"])

    def __read_binary(self, file_data: dict) -> None:
        # Triple -> {"Url": ..., "Sha256": ...}. The set of triples is the set of
        # systems this dependency ships prebuilt for; the checksum is mandatory
        # because a downloaded blob has no other integrity guarantee.
        self.__artifacts: dict[str, BinaryArtifact] = {}
        for triple, spec in file_data["Artifacts"].items():
            self.__artifacts[triple] = BinaryArtifact(url=spec["Url"], sha256=spec["Sha256"])
        if not self.__artifacts:
            raise ModuleGraphError(f"Binary module '{self.name}' declares no artifacts")
        # find_package name defaults to the module name; the archive's config
        # package and the target it exports (via CMakeModularTargets) are what
        # consumers actually link.
        self.__find_package_name: str = file_data.get("FindPackage", self.name)

    def select_artifact(self, triple: str) -> BinaryArtifact:
        artifact = self.__artifacts.get(triple)
        if artifact is None:
            available = ", ".join(sorted(self.__artifacts)) or "none"
            raise ModuleGraphError(
                f"Binary module '{self.name}' has no artifact for system triple '{triple}' (available: {available})"
            )
        return artifact

    def binary_extract_dir(self, triple: str) -> Path:
        """Where the artifact for `triple` is unpacked - beside the manifest, git-ignored."""
        return self.root_dir / ".prebuilt" / triple

    @property
    def artifacts(self) -> dict[str, BinaryArtifact]:
        return self.__artifacts

    @property
    def find_package_name(self) -> str:
        return self.__find_package_name

    @property
    def cmake_file_path(self) -> str:
        return self.__cmake_file_path

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
    def name(self) -> str:
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
    def all_dependencies(self) -> Generator[str, None, None]:
        """Yields all dependencies for this module"""
        yield from self.public_dependencies
        yield from self.private_dependencies

    @property
    def module_type(self) -> ModuleType:
        """Returns the type of module"""
        return self.__module_type

    @property
    def extra_cmake_files(self) -> Generator[str, None, None]:
        yield from self.__extra_cmake_files

    @property
    def source_files(self) -> Iterable[Path]:
        """Yields all source files for module"""

        def suffixes() -> Iterable[str]:
            yield from CPP_SUFFIXES
            yield from HPP_SUFFIXES
            yield from CUDA_SUFFIXES

        for suffix in suffixes():
            yield from self.root_dir.rglob(f"*{suffix}")

    @property
    def should_add_subdirectory(self) -> bool:
        return self.__cmake_add_subdirectory

    @property
    def generate_cmake_file(self) -> bool:
        return self.__generate_cmake_file

    @property
    def cmake_target_name(self) -> str:
        if self.__cmake_target_name is None:
            return self.name
        return self.__cmake_target_name

    @property
    def cmake_exclude_from_all(self) -> bool:
        return self.__cmake_exclude_from_all

    @property
    def cmake_modular_targets(self) -> list[str]:
        return self.__cmake_modular_targets

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

    @property
    def compress_debug_info(self) -> bool:
        return self.__compress_debug_info

    @classmethod
    def glob_files_in(cls, root: Path) -> Iterable[Path]:
        return root.rglob(f"*{yae_constants.MODULE_EXT}")

    @classmethod
    def glob_in(cls, root: Path) -> Generator[Module, None, None]:
        yield from (Module(x) for x in cls.glob_files_in(root))

    @classmethod
    def sorted_glob_in(cls, root: Path) -> list[Module]:
        return sorted(cls.glob_in(root), key=lambda x: x.name)
