from __future__ import annotations

from pathlib import Path
import hashlib
import shutil
import tarfile
import tempfile
import time
import urllib.request

from yae.errors import FetchError
from yae.module import Module
from yae.system_triple import current_system_triple
from yae.yae_logging import get_logger


logger = get_logger(__name__)

# Bump if the extraction layout ever changes so stale unpacks are refetched.
_MARKER_NAME = ".yae-binary-artifact"
_DOWNLOAD_CHUNK = 1 << 20


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
        extract_dir = module.binary_extract_dir(triple)
        marker = extract_dir / _MARKER_NAME

        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == artifact.sha256:
            return

        logger.info("Fetching binary dependency %s (%s)", module.name, triple)
        start_time = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "artifact"
            self.__download(artifact.url, archive)
            self.__verify(archive, artifact.sha256, artifact.url)
            self.__extract(archive, extract_dir)
        marker.write_text(artifact.sha256, encoding="utf-8")
        logger.info("Unpacked %s in %.2fs", module.name, time.time() - start_time)

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
        # Replace any previous unpack wholesale so a refetch cannot blend two
        # versions. The parent is the git-ignored .prebuilt dir in the checkout.
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)
        try:
            with tarfile.open(archive, mode="r:*") as tar:
                self.__safe_extract(tar, extract_dir)
        except tarfile.TarError as err:
            raise FetchError(f"Failed to unpack binary dependency archive {archive.name}: {err}")

    def __safe_extract(self, tar: tarfile.TarFile, extract_dir: Path) -> None:
        # A release archive is trusted (pinned URL + checksum), but a path that
        # escapes the destination would still be a bug worth refusing rather than
        # silently writing outside the tree.
        resolved_root = extract_dir.resolve()
        for member in tar.getmembers():
            target = (extract_dir / member.name).resolve()
            if not target.is_relative_to(resolved_root):
                raise FetchError(f"Refusing archive member outside extraction dir: {member.name}")
        tar.extractall(extract_dir)
