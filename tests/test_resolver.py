import json
from pathlib import Path

import pytest

from yae.cloned_repository_registry import ClonedRepositoryRegistry
from yae.errors import ModuleGraphError
from yae.global_context import GlobalContext
from yae.repository_fetcher import RepositoryFetcher
from yae.resolver import gather_packages


def write_package(path: Path, dependencies: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"dependencies": {"packages": dependencies}}), encoding="utf-8")


@pytest.mark.parametrize("requested", [["a", "b"], ["b", "a"]])
@pytest.mark.parametrize("cycle", [False, True])
def test_shared_checkout_expands_required_packages(tmp_path: Path, monkeypatch, requested: list[str], cycle: bool) -> None:
    project = tmp_path / "project"
    repositories = tmp_path / "repositories"
    shared = repositories / "example/shared/main"
    transitive = repositories / "example/transitive/main"
    shared_link = "https://github.com/example/shared main"
    transitive_link = "https://github.com/example/transitive main"
    write_package(project / "app.package.json", [{"link": shared_link, "packages": requested}])
    write_package(project / "yae-support.package.json", [])
    (project / "yae_project.json").write_text(
        json.dumps({"name": "test", "cpp": {"standard": "23"}}), encoding="utf-8"
    )
    write_package(shared / "a/a.package.json", [{"link": transitive_link, "packages": ["c"]}])
    write_package(shared / "b/b.package.json", [])
    write_package(shared / "unused/unused.package.json", [{"link": transitive_link, "packages": ["missing"]}])
    write_package(transitive / "c.package.json", [{"link": shared_link, "packages": ["a", "b"]}] if cycle else [])
    fetched: list[Path] = []

    def ensure(self, local_dir: Path, git_url: str, git_tag: str) -> bool:
        fetched.append(local_dir)
        assert len(fetched) <= 2
        return (repositories / local_dir).is_dir()

    monkeypatch.setattr(RepositoryFetcher, "ensure", ensure)

    ctx = GlobalContext(project, repositories)
    packages = gather_packages(ctx, RepositoryFetcher(ctx, ClonedRepositoryRegistry(ctx)))

    assert {package.name for package in packages} == {"app", "yae-support", "a", "b", "c"}
    assert fetched == [Path("example/shared/main"), Path("example/transitive/main")]


def test_shared_checkout_rejects_conflicting_dependency_links(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    repositories = tmp_path / "repositories"
    shared = repositories / "example/shared/main"
    write_package(
        project / "app.package.json",
        [{"link": "https://github.com/example/shared main", "packages": ["a", "b"]}],
    )
    write_package(project / "yae-support.package.json", [])
    (project / "yae_project.json").write_text(
        json.dumps({"name": "test", "cpp": {"standard": "23"}}), encoding="utf-8"
    )
    write_package(shared / "a/a.package.json", [])
    write_package(shared / "b/b.package.json", [{"link": "https://github.com/example/shared other", "packages": ["a"]}])
    monkeypatch.setattr(RepositoryFetcher, "ensure", lambda *args: True)

    with pytest.raises(ModuleGraphError, match="Packages with the same address must be identical"):
        ctx = GlobalContext(project, repositories)
        gather_packages(ctx, RepositoryFetcher(ctx, ClonedRepositoryRegistry(ctx)))
