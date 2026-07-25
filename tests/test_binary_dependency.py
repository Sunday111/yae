import hashlib
import json
import tarfile
from pathlib import Path

import pytest

from yae.errors import FetchError
from yae.errors import ModuleGraphError
from yae.binary_artifact_fetcher import BinaryArtifactFetcher
from yae.module import Module
from yae.module import ModuleType
from yae.system_triple import current_system_triple


def write_module(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_archive(directory: Path, files: dict[str, str]) -> tuple[Path, str]:
    """Builds a .tar.gz with the given files and returns (path, sha256)."""
    archive = directory / "artifact.tar.gz"
    with tarfile.open(archive, mode="w:gz") as tar:
        for name, content in files.items():
            member_path = directory / name
            member_path.parent.mkdir(parents=True, exist_ok=True)
            member_path.write_text(content, encoding="utf-8")
            tar.add(member_path, arcname=name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, digest


def binary_module(tmp_path: Path, artifacts: dict) -> Module:
    module_file = tmp_path / "slang.module.json"
    write_module(
        module_file,
        {
            "ModuleType": "Binary",
            "FindPackage": "slang",
            "CMakeModularTargets": ["slang::slang"],
            "Artifacts": artifacts,
        },
    )
    return Module(module_file)


def test_binary_module_parses_artifacts_and_targets(tmp_path: Path) -> None:
    module = binary_module(
        tmp_path,
        {"linux-x86_64": {"Url": "https://example/slang.tar.gz", "Sha256": "abc123"}},
    )
    assert module.module_type == ModuleType.BINARY
    assert module.find_package_name == "slang"
    assert module.cmake_modular_targets == ["slang::slang"]
    artifact = module.select_artifact("linux-x86_64")
    assert artifact.url == "https://example/slang.tar.gz"
    assert artifact.sha256 == "abc123"


def test_find_package_name_defaults_to_module_name(tmp_path: Path) -> None:
    module_file = tmp_path / "slang.module.json"
    write_module(
        module_file,
        {"ModuleType": "Binary", "Artifacts": {"linux-x86_64": {"Url": "u", "Sha256": "s"}}},
    )
    assert Module(module_file).find_package_name == "slang"


def test_select_artifact_missing_triple_raises(tmp_path: Path) -> None:
    module = binary_module(tmp_path, {"linux-x86_64": {"Url": "u", "Sha256": "s"}})
    with pytest.raises(ModuleGraphError, match="no artifact for system triple 'windows-x86_64'"):
        module.select_artifact("windows-x86_64")


def test_empty_artifacts_rejected(tmp_path: Path) -> None:
    module_file = tmp_path / "slang.module.json"
    write_module(module_file, {"ModuleType": "Binary", "Artifacts": {}})
    with pytest.raises(ModuleGraphError, match="declares no artifacts"):
        Module(module_file)


def test_fetch_downloads_verifies_and_extracts(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"lib/cmake/slang/slangConfig.cmake": "# config", "include/slang.h": "// hdr"})

    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})
    BinaryArtifactFetcher().ensure(module)

    extract_dir = module.binary_extract_dir(triple)
    assert (extract_dir / "lib/cmake/slang/slangConfig.cmake").is_file()
    assert (extract_dir / "include/slang.h").is_file()
    assert (extract_dir / ".yae-binary-artifact").read_text().strip() == sha


def test_fetch_is_idempotent_and_reuses_unpack(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "// hdr"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})

    fetcher = BinaryArtifactFetcher()
    fetcher.ensure(module)
    marker = module.binary_extract_dir(triple) / ".yae-binary-artifact"
    first_mtime = marker.stat().st_mtime_ns

    # A second call with the same checksum must not re-extract.
    fetcher.ensure(module)
    assert marker.stat().st_mtime_ns == first_mtime


def test_fetch_rejects_checksum_mismatch(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, _ = make_archive(source, {"include/slang.h": "// hdr"})
    wrong = "0" * 64
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": wrong}})

    with pytest.raises(FetchError, match="Checksum mismatch"):
        BinaryArtifactFetcher().ensure(module)
    # A failed verification must leave nothing behind to be mistaken for a good unpack.
    assert not (module.binary_extract_dir(triple) / ".yae-binary-artifact").exists()
