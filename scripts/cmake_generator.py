"""Utilities to generate cmake files"""

from typing import Iterable, TextIO
from pathlib import Path


class CMakeGenerator:
    """Generates tokens for CMakeLists.txt"""

    def __init__(self, file: TextIO) -> None:
        self.__file = file

    def version_line(self, major: int, minor: int):
        """version line"""
        self.__write(f"cmake_minimum_required(VERSION {major}.{minor})\n")

    def project_line(self, project_name: str):
        """Project line"""
        self.__write(f"project({project_name})\n")

    def add_subdirectory(self, path: Path, is_system: bool = False):
        """add_subdirectory(path)"""
        self.__write(f"add_subdirectory({path.as_posix()}")
        if is_system:
            self.__write(" SYSTEM")
        self.line(")")

    @staticmethod
    def make_file_path(directory: Path) -> Path:
        """Makes cmake file path at specified directory"""
        assert directory.is_dir()
        return directory / "CMakeLists.txt"

    def make_list_variable(self, variable_name: str, values: Iterable):
        self.__write(f"set({variable_name}\n    ")
        self.__write("\n    ".join(values))
        self.line(")")

    def make_paths_list_variable(self, variable_name: str, paths: Iterable[Path]):
        self.make_list_variable(
            variable_name,
            ("${CMAKE_CURRENT_SOURCE_DIR}/" + path.as_posix() for path in paths),
        )

    def add_library(self, library_name: str, library_type: str, sources_variable_name: str):
        self.line(f"add_library({library_name} {library_type} ${{{sources_variable_name}}})")

    def add_executable(self, target_name: str, sources_variable_name: str):
        self.line(f"add_executable({target_name} ${{{sources_variable_name}}})")

    def target_link_libraries(self, target_name: str, access: str, dependencies: list[str]):
        if len(dependencies) > 0:
            delcaration = f"target_link_libraries({target_name} {access} "
            self.__write(delcaration)
            if len(dependencies) < 2:
                self.__write(dependencies[0])
            else:
                space = ""
                self.__write(f"\n{space:{len(delcaration)}}".join(dependencies))
            self.line(")")

    def define_cpp_standard(self, standard: int):
        self.line(f"set(CMAKE_CXX_STANDARD {standard})")

    def require_cpp_standard(self):
        self.line("set(CMAKE_CXX_STANDARD_REQUIRED ON)")

    def disable_cpp_extensions(self):
        self.line("set(CMAKE_CXX_EXTENSIONS OFF)")

    @staticmethod
    def patch_rel_path(rel_path: Path):
        return f"${{CMAKE_CURRENT_SOURCE_DIR}}/{rel_path.as_posix()}"

    def __write(self, text: str):
        self.__file.write(text)

    def line(self, content: str | None = None):
        if content is not None:
            self.__write(content)
        self.__write("\n")

    def include(self, cmake_module_name: str):
        self.line(f"include({cmake_module_name})")

    def target_include_directories(self, target: str, access: str, rel_dirs: str):
        declaration = f"target_include_directories({target} {access} "
        self.__write(declaration)
        space = ""
        self.__write(f"\n{space:{len(declaration)}}".join(self.patch_rel_path(dir) for dir in rel_dirs))
        self.line(")")

    def option(self, name: str, value: str | int | bool) -> bool:
        if isinstance(value, bool):
            self.line(f"option({name} \"\" {'ON' if value else 'OFF'})")
            return True

        print(f'Module {name} has variable "{name}" with unsupported type {type(value)}')
        return False

    def header_comment(self, text: str):
        header_width = 80
        self.line(f"# { text :-^{header_width}}")
