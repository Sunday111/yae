from pathlib import Path
import json


def read_json_file(path: Path) -> dict:
    with open(path, mode="r", encoding="utf-8") as file:
        return json.load(file)


def save_json_to_file(path: Path, data: dict):
    with open(path, mode="w", encoding="utf-8") as file:
        return json.dump(data, file, indent=4, sort_keys=True)
