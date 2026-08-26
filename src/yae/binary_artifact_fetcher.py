from __future__ import annotations

import errno
import hashlib
import os
import shutil
import tarfile
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from yae.errors import FetchError
from yae.module import Module
from yae.system_triple import current_system_triple
from yae.yae_logging import get_logger


logger = get_logger(__name__)

# Bump if the extraction layout ever changes so stale unpacks are refetched.
_MARKER_NAME = ".yae-binary-artifact"
_DOWNLOAD_CHUNK = 1 << 20
_LOCK_RETRY_SECONDS = 0.05


def _is_path_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


@contextmanager
def _exclusive_file_lock(path: Path) -> Iterator[None]:
    with path.open("a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as err:
                    if err.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    time.sleep(_LOCK_RETRY_SECONDS)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class BinaryArtifactFetcher:
    """Downloads, verifies, and unpacks a binary dependency's release archive.

    The counterpart to RepositoryFetcher for `ModuleType.BINARY`: it selects the
    artifact for the host triple, streams it to a temporary file while hashing,
    checks the pinned SHA-256, and extracts once into the module's per-triple
    directory. A marker file records the checksum that produced the current unpack
    so a matching one is reused and a changed pin forces a clean refetch.
    """

    def ensure(self, module: Module) -> None:
        triple = current_system_triple()
        artifact = module.select_artifact(triple)
        try:
            extract_dir = self.__prepare_extract_dir(module, triple)
            lock_path = extract_dir.parent / f".{extract_dir.name}.lock"
            with _exclusive_file_lock(lock_path):
                self.__recover_interrupted_install(extract_dir)
                marker = extract_dir / _MARKER_NAME
                try:
                    marker_matches = (
                        not _is_path_link(extract_dir)
                        and extract_dir.is_dir()
                        and not _is_path_link(marker)
                        and marker.is_file()
                        and marker.read_text(encoding="utf-8").strip() == artifact.sha256
                    )
                except UnicodeDecodeError:
                    marker_matches = False
                if marker_matches:
                    return

                logger.info("Fetching binary dependency %s (%s)", module.name, triple)
                start_time = time.time()
                with tempfile.TemporaryDirectory() as download_dir, tempfile.TemporaryDirectory(
                    dir=extract_dir.parent,
                    prefix=f".{extract_dir.name}-staging-",
                ) as staging_root:
                    archive = Path(download_dir) / "artifact"
                    staged_extract = Path(staging_root) / "extract"
                    staged_extract.mkdir()
                    self.__download(artifact.url, archive)
                    self.__verify(archive, artifact.sha256, artifact.url)
                    self.__extract(archive, staged_extract)
                    staged_marker = staged_extract / _MARKER_NAME
                    if staged_marker.exists() or _is_path_link(staged_marker):
                        raise FetchError(
                            f"Binary dependency archive contains reserved path {_MARKER_NAME}"
                        )
                    staged_marker.write_text(artifact.sha256, encoding="utf-8")
                    self.__replace_extract(staged_extract, extract_dir)
                logger.info("Unpacked %s in %.2fs", module.name, time.time() - start_time)
        except FetchError:
            raise
        except OSError as err:
            raise FetchError(f"Failed to install binary dependency {module.name}: {err}") from err

    def __prepare_extract_dir(self, module: Module, triple: str) -> Path:
        extract_dir = module.binary_extract_dir(triple)
        artifacts_dir = extract_dir.parent
        if _is_path_link(artifacts_dir):
            raise FetchError(
                f"Binary dependency extraction directory must not be a symlink or junction: "
                f"{artifacts_dir}"
            )
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        if artifacts_dir.resolve() != artifacts_dir:
            raise FetchError(
                f"Binary dependency extraction directory must stay within {module.root_dir}: "
                f"{artifacts_dir}"
            )
        if _is_path_link(extract_dir):
            raise FetchError(
                f"Binary dependency extraction directory must not be a symlink or junction: "
                f"{extract_dir}"
            )
        return extract_dir

    def __download(self, url: str, destination: Path) -> None:
        try:
            with urllib.request.urlopen(url) as response, destination.open("wb") as out:
                while chunk := response.read(_DOWNLOAD_CHUNK):
                    out.write(chunk)
        except OSError as err:
            raise FetchError(f"Failed to download binary dependency from {url}: {err}")

    def __verify(self, archive: Path, expected_sha256: str, url: str) -> None:
        digest = hashlib.sha256()
        with archive.open("rb") as file:
            while chunk := file.read(_DOWNLOAD_CHUNK):
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual.lower() != expected_sha256.lower():
            raise FetchError(
                f"Checksum mismatch for {url}: expected {expected_sha256}, got {actual}"
            )

    def __extract(self, archive: Path, extract_dir: Path) -> None:
        try:
            with tarfile.open(archive, mode="r:*") as tar:
                tar.extractall(extract_dir, filter="data")
        except tarfile.TarError as err:
            raise FetchError(f"Failed to unpack binary dependency archive {archive.name}: {err}")

    def __recover_interrupted_install(self, extract_dir: Path) -> None:
        previous_extract = extract_dir.with_name(f".{extract_dir.name}.previous")
        if not previous_extract.exists() and not _is_path_link(previous_extract):
            return
        if extract_dir.is_dir() and not _is_path_link(extract_dir):
            self.__remove_path(previous_extract)
            return
        if _is_path_link(previous_extract) or not previous_extract.is_dir():
            self.__remove_path(previous_extract)
            return
        if extract_dir.exists() or _is_path_link(extract_dir):
            self.__remove_path(extract_dir)
        previous_extract.replace(extract_dir)

    def __replace_extract(self, staged_extract: Path, extract_dir: Path) -> None:
        previous_extract = extract_dir.with_name(f".{extract_dir.name}.previous")
        try:
            if extract_dir.exists() or _is_path_link(extract_dir):
                extract_dir.replace(previous_extract)
            staged_extract.replace(extract_dir)
        except BaseException as install_error:
            try:
                if (
                    not extract_dir.exists()
                    and not _is_path_link(extract_dir)
                    and previous_extract.exists()
                ):
                    previous_extract.replace(extract_dir)
            except OSError as restore_error:
                raise FetchError(
                    f"Failed to install binary dependency and restore {extract_dir}; "
                    f"the previous unpack remains at {previous_extract}: {restore_error}"
                ) from install_error
            if isinstance(install_error, OSError):
                raise FetchError(
                    f"Failed to replace binary dependency at {extract_dir}: {install_error}"
                ) from install_error
            raise

        if previous_extract.exists() or _is_path_link(previous_extract):
            try:
                self.__remove_path(previous_extract)
            except OSError as err:
                logger.warning(
                    "Could not remove previous binary dependency unpack %s: %s",
                    previous_extract,
                    err,
                )

    def __remove_path(self, path: Path) -> None:
        if path.is_junction():
            path.rmdir()
        elif path.is_symlink() or not path.is_dir():
            path.unlink()
        else:
            shutil.rmtree(path)
