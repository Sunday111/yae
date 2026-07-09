from __future__ import annotations

from pathlib import Path
import json


LOCAL_CONFIG_FILE_NAME = "local-config.json"


def read_project_config(project_dir: Path) -> dict:
    with open(project_dir / "yae_project.json", mode="r", encoding="utf-8") as file:
        return json.load(file)


def read_local_config(project_dir: Path) -> dict:
    local_config_path = project_dir / LOCAL_CONFIG_FILE_NAME
    if not local_config_path.exists():
        return {}

    with open(local_config_path, mode="r", encoding="utf-8") as file:
        return json.load(file)


def merge_config(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result


def get_default_configuration(project_dir: Path) -> dict:
    project_config = read_project_config(project_dir)
    default_configuration = project_config.get("default_configuration", {})

    local_config = read_local_config(project_dir)
    if not local_config:
        return default_configuration

    local_default_configuration = local_config.get("default_configuration", local_config)
    return merge_config(default_configuration, local_default_configuration)
