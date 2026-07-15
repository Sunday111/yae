"""Tests for yae-support's staging script.

The script lives in yae-support because generated projects must build without yae,
but it is yae that decides how it is called, so it is tested here.
"""

from __future__ import annotations

import os
import shutil

import pytest

from pathlib import Path

from yae.tests.support_scripts import load_stage_directories


@pytest.fixture(scope="module")
def staging():
    """The script under test, loaded from the yae-support checkout.

    A fixture rather than an import: without a checkout this fails these tests only,
    instead of aborting collection of the whole suite.
    """
    return load_stage_directories()


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_older(path: Path, seconds: int = 10) -> None:
    """Backdates a file so staging sees it as older than what is already staged."""
    stamp = path.stat().st_mtime - seconds
    os.utime(path, (stamp, stamp))


def manifest(tmp_path: Path, name: str = "module") -> Path:
    return tmp_path / "build" / f"{name}.manifest"


def staged_files(destination: Path) -> set[str]:
    return {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}


def test_sources_are_copied_into_the_destination(staging, tmp_path: Path) -> None:
    source = tmp_path / "source"
    write(source / "shaders/a.frag", "a")
    write(source / "shaders/nested/b.vert", "b")
    destination = tmp_path / "out"

    copied, removed = staging.stage_directories(destination, [source], manifest(tmp_path))

    assert staged_files(destination) == {"shaders/a.frag", "shaders/nested/b.vert"}
    assert (destination / "shaders/nested/b.vert").read_text(encoding="utf-8") == "b"
    assert (copied, removed) == (2, 0)


def test_several_sources_are_merged_into_one_destination(staging, tmp_path: Path) -> None:
    """A module can declare more than one directory staged to the same place."""
    library = tmp_path / "library"
    write(library / "shaders/lib/a.frag", "a")
    example = tmp_path / "example"
    write(example / "shaders/example/b.frag", "b")
    destination = tmp_path / "out"

    staging.stage_directories(destination, [library, example], manifest(tmp_path))

    assert staged_files(destination) == {"shaders/lib/a.frag", "shaders/example/b.frag"}


def test_staging_again_does_nothing(staging, tmp_path: Path) -> None:
    source = tmp_path / "source"
    write(source / "a.frag", "a")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [source], manifest(tmp_path))
    stamp_before = (destination / "a.frag").stat().st_mtime_ns

    copied, removed = staging.stage_directories(destination, [source], manifest(tmp_path))

    assert (copied, removed) == (0, 0)
    assert (destination / "a.frag").stat().st_mtime_ns == stamp_before


def test_changed_source_is_restaged(staging, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source_file = write(source / "a.frag", "before")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [source], manifest(tmp_path))

    write(source / "a.frag", "after")
    copied, removed = staging.stage_directories(destination, [source], manifest(tmp_path))

    assert (destination / "a.frag").read_text(encoding="utf-8") == "after"
    assert (copied, removed) == (1, 0)
    assert source_file.exists()


def test_deleted_source_is_removed_from_the_destination(staging, tmp_path: Path) -> None:
    """A file whose source is gone would otherwise still be found by whatever runs
    from the destination."""
    source = tmp_path / "source"
    write(source / "keep.frag", "keep")
    removed_file = write(source / "gone.frag", "gone")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [source], manifest(tmp_path))

    removed_file.unlink()
    copied, removed = staging.stage_directories(destination, [source], manifest(tmp_path))

    assert staged_files(destination) == {"keep.frag"}
    assert (copied, removed) == (0, 1)


def test_a_module_does_not_remove_another_modules_files(staging, tmp_path: Path) -> None:
    """The whole point of the manifest. Modules stage into one directory, so a module
    deleting everything its own sources do not provide would take the other modules'
    files with it."""
    library = tmp_path / "library"
    write(library / "shaders/lib/a.frag", "a")
    example = tmp_path / "example"
    write(example / "shaders/example/b.frag", "b")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [library], manifest(tmp_path, "library"))
    staging.stage_directories(destination, [example], manifest(tmp_path, "example"))

    # The library stages again, knowing nothing about the example's file.
    copied, removed = staging.stage_directories(destination, [library], manifest(tmp_path, "library"))

    assert staged_files(destination) == {"shaders/lib/a.frag", "shaders/example/b.frag"}
    assert (copied, removed) == (0, 0)


def test_a_module_removes_only_its_own_stale_files(staging, tmp_path: Path) -> None:
    library = tmp_path / "library"
    library_file = write(library / "shaders/lib/a.frag", "a")
    example = tmp_path / "example"
    write(example / "shaders/example/b.frag", "b")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [library], manifest(tmp_path, "library"))
    staging.stage_directories(destination, [example], manifest(tmp_path, "example"))

    library_file.unlink()
    copied, removed = staging.stage_directories(destination, [library], manifest(tmp_path, "library"))

    assert staged_files(destination) == {"shaders/example/b.frag"}
    assert (copied, removed) == (0, 1)


def test_files_the_module_never_staged_are_left_alone(staging, tmp_path: Path) -> None:
    """A module only knows what it staged itself, so anything else in the destination -
    another module's file, or something left there by hand - is not its to remove."""
    source = tmp_path / "source"
    write(source / "a.frag", "a")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [source], manifest(tmp_path))
    write(destination / "left_by_hand.txt", "hand written")

    copied, removed = staging.stage_directories(destination, [source], manifest(tmp_path))

    assert staged_files(destination) == {"a.frag", "left_by_hand.txt"}
    assert (copied, removed) == (0, 0)


def test_manifest_records_what_was_staged(staging, tmp_path: Path) -> None:
    source = tmp_path / "source"
    write(source / "shaders/a.frag", "a")
    write(source / "b.txt", "b")
    destination = tmp_path / "out"
    manifest_path = manifest(tmp_path)

    staging.stage_directories(destination, [source], manifest_path)

    assert manifest_path.read_text(encoding="utf-8").split() == ["b.txt", "shaders/a.frag"]


def test_staging_recovers_when_the_destination_was_wiped(staging, tmp_path: Path) -> None:
    """The manifest still lists the files, but they are gone: they must come back rather
    than be treated as already staged."""
    source = tmp_path / "source"
    write(source / "a.frag", "a")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [source], manifest(tmp_path))

    shutil.rmtree(destination)
    copied, removed = staging.stage_directories(destination, [source], manifest(tmp_path))

    assert staged_files(destination) == {"a.frag"}
    assert (copied, removed) == (1, 0)


def test_directories_left_empty_are_removed(staging, tmp_path: Path) -> None:
    source = tmp_path / "source"
    write(source / "nested/deep/a.frag", "a")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [source], manifest(tmp_path))

    (source / "nested/deep/a.frag").unlink()
    staging.stage_directories(destination, [source], manifest(tmp_path))

    assert not (destination / "nested").exists()


def test_two_sources_claiming_the_same_path_is_an_error(staging, tmp_path: Path) -> None:
    """They would both be copied to the same place and the winner would depend on the
    order the directories happen to be listed in."""
    first = tmp_path / "first"
    write(first / "shaders/a.frag", "first")
    second = tmp_path / "second"
    write(second / "shaders/a.frag", "second")
    destination = tmp_path / "out"

    with pytest.raises(staging.StagingError, match="provided by two sources"):
        staging.stage_directories(destination, [first, second], manifest(tmp_path))


def test_missing_source_directory_is_an_error(staging, tmp_path: Path) -> None:
    with pytest.raises(staging.StagingError, match="does not exist"):
        staging.stage_directories(tmp_path / "out", [tmp_path / "missing"], manifest(tmp_path))


def test_staged_file_newer_than_its_source_is_left_alone(staging, tmp_path: Path) -> None:
    """Staging copies what is newer, so a staged file that is already newer than its
    source is left as it is.

    The cost of comparing this way rather than for any difference: a source that somehow
    becomes older than what is staged - restored from an archive that kept its
    timestamps, say - is not restaged. Checkouts write current timestamps, so this does
    not come up in practice.
    """
    source = tmp_path / "source"
    write(source / "a.frag", "from source")
    destination = tmp_path / "out"
    staging.stage_directories(destination, [source], manifest(tmp_path))

    write(destination / "a.frag", "edited in place")
    make_older(source / "a.frag")
    copied, removed = staging.stage_directories(destination, [source], manifest(tmp_path))

    assert (destination / "a.frag").read_text(encoding="utf-8") == "edited in place"
    assert (copied, removed) == (0, 0)
