from __future__ import annotations

from pathlib import Path
from typing import Generator, Iterable

from yae import json_utils
from yae import yae_constants
from yae.errors import ModuleGraphError
from yae.github_link import GitHubLink


class Package:
    """
    Package is a collection of modules (or packages, in the future)
    It also specifies the list of required external packages
    """

    __file_ext = yae_constants.PACKAGE_EXT

    def __init__(self, path_to_file: Path):
        self.__root_dir = path_to_file.parent
        json = json_utils.read_json_file(path_to_file)
        self.__name = path_to_file.name.replace(yae_constants.PACKAGE_EXT, "")
        self.__read_modules_dir(json)
        self.__read_dependencies(json)

    def __read_modules_dir(self, json: dict):
        from_json = json.get("modules_dir", None)
        if from_json is None:
            self.__modules_dir = self.root_dir
        else:
            self.__modules_dir = self.root_dir / from_json

    def __read_dependencies(self, json: dict):
        # init defaults
        # Key: package name
        # Value: where it can be fetched
        self.__dependencies: dict[str, GitHubLink] = dict()
        dependency_json = json.get("dependencies", dict())
        packages = dependency_json.get("packages", list())
        for package_json in packages:
            link = GitHubLink.parse(package_json["link"])
            for package_name in package_json["packages"]:
                if package_name in self.__dependencies:
                    raise ModuleGraphError(f"Package '{package_name}' is declared as a dependency more than once")
                self.__dependencies[package_name] = link

    @property
    def root_dir(self) -> Path:
        return self.__root_dir

    @property
    def modules_dir(self) -> Path:
        return self.__modules_dir

    @property
    def dependencies(self) -> Generator[tuple[str, GitHubLink], None, None]:
        yield from self.__dependencies.items()

    @property
    def name(self) -> str:
        return self.__name

    @classmethod
    def glob_files_in(cls, root: Path) -> Iterable[Path]:
        return root.rglob(f"*{yae_constants.PACKAGE_EXT}")

    @classmethod
    def glob_in(cls, root: Path) -> Generator["Package", None, None]:
        yield from (Package(x) for x in cls.glob_files_in(root))
