import project_config
from pathlib import Path
import argparse
import json_utils
import subprocess

SCRIPT_DIR = Path(__file__).parent.resolve()
YAE_ROOT = SCRIPT_DIR.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_dir", type=Path, required=True, help="Path to directory with your project")
    parser.add_argument(
        "--external_modules_dir", type=Path, required=False, help="Path to directory where external rpositories live"
    )
    cli_parameters = parser.parse_args()
    project_dir: Path = cli_parameters.project_dir

    config = project_config.ProjectConfig(project_dir, cloned_repositories_dir=cli_parameters.external_modules_dir)
    paths: list[Path] = [YAE_ROOT]

    registry_path = config.cloned_modules_registry_file
    if registry_path.exists() and registry_path.is_file():
        registry = json_utils.read_json_file(registry_path)
        for local_path in registry.keys():
            paths.append(config.cloned_repos_dir / local_path)
    else:
        print(f"{registry_path} does not exist or not a file. Skipping checking cloned modules")

    for path in paths:
        result = subprocess.run(args=["git", "diff", "--quiet"], cwd=path)
        if result.returncode != 0:
            print(path)
            subprocess.run(args=["git", "status", "--short"], check=True, cwd=path)
            print()


if __name__ == "__main__":
    main()
