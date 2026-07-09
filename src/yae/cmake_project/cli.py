from __future__ import annotations

from pathlib import Path
import argparse

from yae.cmake_project import generate_project_files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_dir", type=Path, required=True, help="Path to directory with your project")
    parser.add_argument(
        "--cloned_repositories_dir",
        type=Path,
        required=False,
        help="Path to directory where cloned repositories live",
    )
    parser.add_argument("--clone-progress", action="store_true", help="Show git clone progress while fetching repositories")
    cli_parameters = parser.parse_args()
    generate_project_files(
        project_dir=cli_parameters.project_dir,
        cloned_repositories_dir=cli_parameters.cloned_repositories_dir,
        show_clone_progress=cli_parameters.clone_progress,
    )
