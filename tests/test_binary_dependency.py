import errno
import hashlib
import json
import stat
import sys
import tarfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from yae import binary_artifact_fetcher
from yae.binary_artifact_fetcher import BinaryArtifactFetcher
from yae.errors import FetchError
from yae.errors import ModuleGraphError
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


def test_fetch_uses_normal_directory_permissions(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "// hdr"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()

    BinaryArtifactFetcher().ensure(module)

    assert stat.S_IMODE(module.binary_extract_dir(triple).stat().st_mode) == stat.S_IMODE(reference_dir.stat().st_mode)


def test_fetch_rejects_a_symlinked_artifact_directory(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "// hdr"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})
    outside = tmp_path / "outside"
    outside.mkdir()
    (module.root_dir / ".prebuilt").symlink_to(outside, target_is_directory=True)

    with pytest.raises(FetchError, match="must not be a symlink"):
        BinaryArtifactFetcher().ensure(module)

    assert not any(outside.iterdir())


def test_fetch_rejects_a_junction_artifact_directory(tmp_path: Path, monkeypatch) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "// hdr"})
    module = binary_module(
        tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}}
    )
    artifacts_dir = module.root_dir / ".prebuilt"
    original_is_junction = Path.is_junction
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == artifacts_dir or original_is_junction(path),
    )

    with pytest.raises(FetchError, match="must not be a symlink or junction"):
        BinaryArtifactFetcher().ensure(module)

    assert not artifacts_dir.exists()


def test_fetch_replaces_an_install_with_a_corrupt_marker(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "// fresh"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})
    extract_dir = module.binary_extract_dir(triple)
    extract_dir.mkdir(parents=True)
    (extract_dir / ".yae-binary-artifact").write_bytes(b"\xff")
    (extract_dir / "stale").write_text("old", encoding="utf-8")

    BinaryArtifactFetcher().ensure(module)

    assert (extract_dir / "include/slang.h").read_text(encoding="utf-8") == "// fresh"
    assert not (extract_dir / "stale").exists()
    assert (extract_dir / ".yae-binary-artifact").read_text(encoding="utf-8").strip() == sha


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


def test_failed_replacement_preserves_the_previous_unpack(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "working"})
    module_dir = tmp_path / "mod"
    module = binary_module(module_dir, {triple: {"Url": archive.as_uri(), "Sha256": sha}})
    fetcher = BinaryArtifactFetcher()
    fetcher.ensure(module)

    invalid_archive = tmp_path / "invalid.tar.gz"
    invalid_archive.write_text("not an archive", encoding="utf-8")
    invalid_sha = hashlib.sha256(invalid_archive.read_bytes()).hexdigest()
    replacement = binary_module(
        module_dir,
        {triple: {"Url": invalid_archive.as_uri(), "Sha256": invalid_sha}},
    )

    with pytest.raises(FetchError, match="Failed to unpack"):
        fetcher.ensure(replacement)

    extract_dir = module.binary_extract_dir(triple)
    assert (extract_dir / "include/slang.h").read_text(encoding="utf-8") == "working"
    assert (extract_dir / ".yae-binary-artifact").read_text(encoding="utf-8") == sha


def test_interrupted_replacement_restores_the_previous_unpack(tmp_path: Path, monkeypatch) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    first_archive, first_sha = make_archive(source, {"include/slang.h": "working"})
    module_dir = tmp_path / "mod"
    first_module = binary_module(module_dir, {triple: {"Url": first_archive.as_uri(), "Sha256": first_sha}})
    BinaryArtifactFetcher().ensure(first_module)

    replacement_source = tmp_path / "replacement"
    replacement_source.mkdir()
    replacement_archive, replacement_sha = make_archive(replacement_source, {"include/slang.h": "replacement"})
    replacement_module = binary_module(
        module_dir,
        {triple: {"Url": replacement_archive.as_uri(), "Sha256": replacement_sha}},
    )
    extract_dir = first_module.binary_extract_dir(triple)
    original_replace = Path.replace

    def interrupt_staged_install(path: Path, target: Path) -> Path:
        if path.name == "extract" and Path(target) == extract_dir:
            raise KeyboardInterrupt
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", interrupt_staged_install)
    with pytest.raises(KeyboardInterrupt):
        BinaryArtifactFetcher().ensure(replacement_module)

    assert (extract_dir / "include/slang.h").read_text(encoding="utf-8") == "working"
    assert (extract_dir / ".yae-binary-artifact").read_text(encoding="utf-8") == first_sha


@pytest.mark.parametrize("symlink", [False, True])
def test_fetch_cleans_a_malformed_previous_unpack(tmp_path: Path, symlink: bool) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "working"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})
    fetcher = BinaryArtifactFetcher()
    fetcher.ensure(module)
    extract_dir = module.binary_extract_dir(triple)
    previous_extract = extract_dir.with_name(f".{extract_dir.name}.previous")
    if symlink:
        previous_extract.symlink_to("missing")
    else:
        previous_extract.write_text("invalid", encoding="utf-8")

    fetcher.ensure(module)

    assert not previous_extract.exists()
    assert not previous_extract.is_symlink()
    assert (extract_dir / "include/slang.h").read_text(encoding="utf-8") == "working"


def test_fetch_does_not_restore_a_symlinked_previous_unpack(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "verified"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})
    extract_dir = module.binary_extract_dir(triple)
    extract_dir.parent.mkdir(parents=True)
    previous_extract = extract_dir.with_name(f".{extract_dir.name}.previous")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / ".yae-binary-artifact").write_text(sha, encoding="utf-8")
    (outside / "unverified").write_text("outside", encoding="utf-8")
    previous_extract.symlink_to(outside, target_is_directory=True)

    BinaryArtifactFetcher().ensure(module)

    assert not extract_dir.is_symlink()
    assert (extract_dir / "include/slang.h").read_text(encoding="utf-8") == "verified"
    assert (outside / "unverified").read_text(encoding="utf-8") == "outside"


def test_concurrent_fetches_share_one_install(tmp_path: Path, monkeypatch) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "// hdr"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})
    original_download = getattr(BinaryArtifactFetcher, "_BinaryArtifactFetcher__download")
    first_download_started = threading.Event()
    release_first_download = threading.Event()
    second_fetch_started = threading.Event()
    download_count = 0

    def slow_download(fetcher: BinaryArtifactFetcher, url: str, destination: Path) -> None:
        nonlocal download_count
        download_count += 1
        first_download_started.set()
        assert release_first_download.wait(timeout=5)
        original_download(fetcher, url, destination)

    def second_fetch() -> None:
        second_fetch_started.set()
        BinaryArtifactFetcher().ensure(module)

    monkeypatch.setattr(BinaryArtifactFetcher, "_BinaryArtifactFetcher__download", slow_download)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(BinaryArtifactFetcher().ensure, module)
        assert first_download_started.wait(timeout=5)
        second = executor.submit(second_fetch)
        assert second_fetch_started.wait(timeout=5)
        time.sleep(0.05)
        release_first_download.set()
        first.result(timeout=5)
        second.result(timeout=5)

    assert download_count == 1


def test_windows_lock_does_not_retry_permanent_errors(tmp_path: Path, monkeypatch) -> None:
    def fail_lock(file_descriptor: int, mode: int, size: int) -> None:
        raise OSError(errno.EIO, "locking unavailable")

    fake_msvcrt = SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=fail_lock)
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)
    monkeypatch.setattr(binary_artifact_fetcher.os, "name", "nt")

    with pytest.raises(OSError, match="locking unavailable"):
        with binary_artifact_fetcher._exclusive_file_lock(tmp_path / "artifact.lock"):
            pass


def test_extraction_io_errors_are_reported_as_fetch_errors(tmp_path: Path, monkeypatch) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {"include/slang.h": "// hdr"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})

    def fail_extract(*args, **kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(tarfile.TarFile, "extractall", fail_extract)
    with pytest.raises(FetchError, match="Failed to install binary dependency slang: disk full"):
        BinaryArtifactFetcher().ensure(module)


def test_fetch_rejects_archive_links_that_escape_the_extract_dir(tmp_path: Path) -> None:
    triple = current_system_triple()
    archive = tmp_path / "artifact.tar.gz"
    with tarfile.open(archive, mode="w:gz") as tar:
        link = tarfile.TarInfo("include")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        tar.addfile(link)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})

    with pytest.raises(FetchError, match="Failed to unpack"):
        BinaryArtifactFetcher().ensure(module)

    assert not (tmp_path / "outside").exists()
    assert not module.binary_extract_dir(triple).exists()


def test_fetch_rejects_an_archive_owned_install_marker(tmp_path: Path) -> None:
    triple = current_system_triple()
    source = tmp_path / "src"
    source.mkdir()
    archive, sha = make_archive(source, {".yae-binary-artifact": "forged", "include/slang.h": "// hdr"})
    module = binary_module(tmp_path / "mod", {triple: {"Url": archive.as_uri(), "Sha256": sha}})

    with pytest.raises(FetchError, match="archive contains reserved path"):
        BinaryArtifactFetcher().ensure(module)

    assert not module.binary_extract_dir(triple).exists()
