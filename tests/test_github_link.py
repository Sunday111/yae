from pathlib import Path

from yae.github_link import GitHubLink


def test_default_ref_is_part_of_local_path() -> None:
    link = GitHubLink.parse("https://github.com/Sunday111/klgl")

    assert link.url == "https://github.com/Sunday111/klgl"
    assert link.tag == "main"
    assert link.subdir == Path("Sunday111/klgl/main")


def test_explicit_ref_is_part_of_local_path() -> None:
    link = GitHubLink.parse("https://github.com/Sunday111/klgl v1.2.3")

    assert link.url == "https://github.com/Sunday111/klgl"
    assert link.tag == "v1.2.3"
    assert link.subdir == Path("Sunday111/klgl/v1.2.3")


def test_ref_path_replaces_slashes() -> None:
    link = GitHubLink.parse("https://github.com/Sunday111/klgl feature/rendering")

    assert link.url == "https://github.com/Sunday111/klgl"
    assert link.tag == "feature/rendering"
    assert link.subdir == Path("Sunday111/klgl/feature_rendering")
