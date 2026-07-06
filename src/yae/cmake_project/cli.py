from __future__ import annotations

from pathlib import Path
import argparse

from yae.cmake_project import generate_project_files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_dir", type=Path, required=True, help="Path to directory with your project")
    parser.add_argument(
        "--external_modules_dir",
        type=Path,
        required=False,
        help="Path to directory where external repositories live",
    )
    cli_parameters = parser.parse_args()
    generate_project_files(
        project_dir=cli_parameters.project_dir,
        external_modules_dir=cli_parameters.external_modules_dir,
    )
