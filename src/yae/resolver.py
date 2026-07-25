from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import itertools

from yae.binary_artifact_fetcher import BinaryArtifactFetcher
from yae.cloned_repository_registry import ClonedRepositoryRegistry
from yae.errors import FetchError
from yae.errors import ModuleGraphError
from yae.github_link import GitHubLink
from yae.global_context import GlobalContext
from yae.module import Module
from yae.module import ModuleType
from yae.module_registry import ModuleRegistry
from yae.package import Package
from yae.repository_fetcher import RepositoryFetcher
from yae.yae_logging import get_logger


logger = get_logger(__name__)

YAE_SUPPORT_PACKAGE_NAME = "yae-support"


class ModuleOrigin(Enum):
    PROJECT = "project"
    SUPPORT = "support"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ResolvedProject:
    context: GlobalContext
    packages: list[Package]
    module_registry: ModuleRegistry
    module_origins: dict[str, ModuleOrigin]

    @property
    def support_package(self) -> Package:
        return next(package for package in self.packages if package.name == YAE_SUPPORT_PACKAGE_NAME)


def gather_packages(ctx: GlobalContext, fetcher: RepositoryFetcher) -> list[Package]:
    local_packages: dict[str, Package] = {}
    available_packages: dict[str, tuple[Package, GitHubLink]] = {}
    packages_to_fetch: list[tuple[str, GitHubLink]] = []
    required_packages: set[str] = set()

    for package in ctx.project_config.packages:
        if package.name in local_packages:
            raise ModuleGraphError(f"Duplicate local package name: {package.name}")
        local_packages[package.name] = package
        required_packages.add(package.name)
        for name, link in package.dependencies:
            if name in local_packages:
                continue
            packages_to_fetch.append((name, link))

    required_packages.add(YAE_SUPPORT_PACKAGE_NAME)
    if YAE_SUPPORT_PACKAGE_NAME not in local_packages:
        packages_to_fetch.append((YAE_SUPPORT_PACKAGE_NAME, ctx.project_config.yae_support_link))

    while packages_to_fetch:
        name, link = packages_to_fetch.pop()
        required_packages.add(name)

        if name in local_packages:
            continue

        if name in available_packages:
            _, existing_link = available_packages[name]
            if link == existing_link:
                continue
            raise ModuleGraphError(
                f"Packages with the same address must be identical. Existing: {existing_link.url} {existing_link.tag} {existing_link.subdir}. New one: {link.url} {link.tag} {link.subdir}"
            )

        if not fetcher.ensure(link.subdir, link.url, link.tag):
            raise FetchError(f"Failed to fetch: {link.url}. Check it exists and has {link.tag} branch or tag")

        repo_root = ctx.project_config.cloned_repositories_dir / link.subdir
        for package in Package.glob_in(repo_root):
            if package.name in available_packages:
                raise ModuleGraphError(f"Duplicate package name across checkouts: {package.name}")
            available_packages[package.name] = (package, link)
            if package.name in required_packages:
                packages_to_fetch.extend(package.dependencies)

        if name not in available_packages:
            raise ModuleGraphError(f"Could not find package {name} at {repo_root.as_posix()} ({link.url} {link.tag})")

    return list(
        filter(
            lambda package: package.name in required_packages,
            itertools.chain(local_packages.values(), (package for package, _ in available_packages.values())),
        )
    )


def gather_modules(
    ctx: GlobalContext,
    packages: list[Package],
    fetcher: RepositoryFetcher,
) -> tuple[ModuleRegistry, dict[str, ModuleOrigin]]:
    module_registry = ModuleRegistry()
    module_origins: dict[str, ModuleOrigin] = {}
    add_module_errors: list[str] = []
    binary_fetcher = BinaryArtifactFetcher()

    for package in packages:
        origin = get_package_origin(ctx, package)
        for module in Module.sorted_glob_in(package.modules_dir):
            if not module_registry.add_one(module):
                add_module_errors.append(f"Failed to add module {module.root_dir.as_posix()} from package {package.name}")
                continue

            module_origins[module.name] = origin
            if module.module_type == ModuleType.GITCLONE:
                if not fetcher.ensure(module.local_path, module.git_url, module.git_tag):
                    add_module_errors.append(
                        f"Failed to clone this uri: {module.git_url}. Check it exists and has {module.git_tag} branch or tag"
                    )
            elif module.module_type == ModuleType.BINARY:
                try:
                    binary_fetcher.ensure(module)
                except FetchError as err:
                    add_module_errors.append(str(err))

    if add_module_errors:
        for error in add_module_errors:
            logger.error("%s", error)
        raise ModuleGraphError("Failed to add some modules!")

    return module_registry, module_origins


def get_package_origin(ctx: GlobalContext, package: Package) -> ModuleOrigin:
    if package.name == YAE_SUPPORT_PACKAGE_NAME:
        return ModuleOrigin.SUPPORT
    is_nested_external_package = (
        ctx.project_config.cloned_repositories_dir.is_relative_to(ctx.root_dir)
        and package.root_dir.is_relative_to(ctx.project_config.cloned_repositories_dir)
    )
    if (
        package.root_dir.is_relative_to(ctx.root_dir)
        and not package.root_dir.is_relative_to(ctx.project_config.default_cloned_repositories_dir)
        and not is_nested_external_package
    ):
        return ModuleOrigin.PROJECT
    return ModuleOrigin.EXTERNAL


def resolve_project(
    project_dir: Path,
    cloned_repositories_dir: Path | None = None,
    show_clone_progress: bool = False,
) -> ResolvedProject:
    if not project_dir.is_absolute():
        project_dir = project_dir.absolute()
    project_dir = project_dir.resolve()

    ctx = GlobalContext(
        project_root=project_dir,
        cloned_repositories_dir=cloned_repositories_dir,
        show_clone_progress=show_clone_progress,
    )
    repo_registry = ClonedRepositoryRegistry(ctx)
    fetcher = RepositoryFetcher(ctx, repo_registry)
    packages = gather_packages(ctx, fetcher)
    module_registry, module_origins = gather_modules(ctx, packages, fetcher)

    if not module_registry.ensure_single_module_rules():
        raise ModuleGraphError("Module rules are invalid")
    if not module_registry.ensure_dependency_graph_is_valid():
        raise ModuleGraphError("Module dependency graph is invalid")

    return ResolvedProject(
        context=ctx,
        packages=packages,
        module_registry=module_registry,
        module_origins=module_origins,
    )
