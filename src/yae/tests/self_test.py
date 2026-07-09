from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

from yae.cmake_project.paths import CMakePathResolver
from yae.global_context import GlobalContext
from yae.project_config import EXTERNAL_MODULES_DIR_ENV
from yae.project_config import ProjectConfig


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)


@contextmanager
def temporary_environment(name: str, value: str | None) -> Iterator[None]:
    old_value = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value

    try:
        yield
    finally:
        if old_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old_value


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=4), encoding="utf-8")


def run_self_test(yae_root: Path) -> None:
    fixture_dir = yae_root / "tests" / "fixtures" / "minimal_project"
    external_modules_dir = yae_root / ".cache" / "self-test-repositories"

    with tempfile.TemporaryDirectory(prefix="yae-self-test-") as temp_dir:
        project_dir = Path(temp_dir) / "minimal_project"
        shutil.copytree(fixture_dir, project_dir)

        yae = (yae_root / "yae").as_posix()
        external_arg = f"--external_modules_dir={external_modules_dir}"

        list_result = run([yae, "list", "--plain", external_arg], cwd=project_dir)
        expected_modules = {
            "project  executable self_test_app",
            "project  library    self_test_lib",
        }
        listed_modules = {
            line for line in list_result.stdout.splitlines() if line.startswith(("project ", "support ", "external "))
        }
        if listed_modules != expected_modules:
            raise RuntimeError(f"Unexpected default list output:\n{list_result.stdout}")

        run([yae, "configure", external_arg], cwd=project_dir)
        run([yae, "build", external_arg], cwd=project_dir)

        content_file = project_dir / "build" / "bin" / "content" / "self_test.txt"
        if content_file.read_text(encoding="utf-8").strip() != "content copied":
            raise RuntimeError(f"Expected copied content at {content_file}")

        run_external_modules_dir_tests(fixture_dir, Path(temp_dir))


def run_external_modules_dir_tests(fixture_dir: Path, temp_dir: Path) -> None:
    project_dir = temp_dir / "external_modules_dir_project"
    shutil.copytree(fixture_dir, project_dir)

    cli_dir = temp_dir / "cli-repositories"
    local_dir = temp_dir / "local-repositories"
    nested_local_dir = temp_dir / "nested-local-repositories"
    env_dir = temp_dir / "env-repositories"

    with temporary_environment(EXTERNAL_MODULES_DIR_ENV, None):
        config = ProjectConfig(project_dir, cloned_repositories_dir=None)
        if config.cloned_repos_dir != project_dir / "cloned_repositories":
            raise RuntimeError(f"Expected project-local default, got {config.cloned_repos_dir}")

    with temporary_environment(EXTERNAL_MODULES_DIR_ENV, env_dir.as_posix()):
        config = ProjectConfig(project_dir, cloned_repositories_dir=None)
        if config.cloned_repos_dir != env_dir:
            raise RuntimeError(f"Expected environment override, got {config.cloned_repos_dir}")

        write_json(project_dir / "local-config.json", {"external_modules_dir": local_dir.as_posix()})
        config = ProjectConfig(project_dir, cloned_repositories_dir=None)
        if config.cloned_repos_dir != local_dir:
            raise RuntimeError(f"Expected local-config override, got {config.cloned_repos_dir}")

        config = ProjectConfig(project_dir, cloned_repositories_dir=cli_dir)
        if config.cloned_repos_dir != cli_dir:
            raise RuntimeError(f"Expected CLI override, got {config.cloned_repos_dir}")

        write_json(project_dir / "local-config.json", {"default_configuration": {"cloned_repositories_dir": nested_local_dir.as_posix()}})
        config = ProjectConfig(project_dir, cloned_repositories_dir=None)
        if config.cloned_repos_dir != nested_local_dir:
            raise RuntimeError(f"Expected nested local-config override, got {config.cloned_repos_dir}")

    ctx = GlobalContext(project_root=project_dir, external_modules_dir=env_dir)
    default_cmake_value = CMakePathResolver(ctx).emit_external_modules_dir()
    expected_cmake_value = "${CMAKE_CURRENT_SOURCE_DIR}/cloned_repositories"
    if default_cmake_value != expected_cmake_value:
        raise RuntimeError(f"Expected generated CMake default {expected_cmake_value}, got {default_cmake_value}")
