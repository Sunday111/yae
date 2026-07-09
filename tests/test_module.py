import json
from pathlib import Path

from yae.module import Module


def write_module(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_github_gitclone_local_path_includes_ref(tmp_path: Path) -> None:
    module_file = tmp_path / "dependency.module.json"
    write_module(
        module_file,
        {
            "ModuleType": "GitClone",
            "GitUrl": "https://github.com/Sunday111/klgl",
            "GitTag": "feature/rendering",
            "LocalPath": "legacy/path",
        },
    )

    assert Module(module_file).local_path == Path("Sunday111/feature_rendering/klgl")


def test_non_github_gitclone_local_path_uses_declared_path(tmp_path: Path) -> None:
    module_file = tmp_path / "dependency.module.json"
    write_module(
        module_file,
        {
            "ModuleType": "GitClone",
            "GitUrl": "https://example.com/vendor/repo",
            "GitTag": "main",
            "LocalPath": "vendor/repo",
        },
    )

    assert Module(module_file).local_path == Path("vendor/repo")
