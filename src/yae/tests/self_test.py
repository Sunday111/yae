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
from yae.settings import CLONED_REPOSITORIES_DIR_ENV
from yae.settings import PROJECT_DIR_ENV
from yae.settings import ResolvedSettings


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
    cloned_repositories_dir = yae_root / ".cache" / "self-test-repositories"

    with tempfile.TemporaryDirectory(prefix="yae-self-test-") as temp_dir:
        project_dir = Path(temp_dir) / "minimal_project"
        shutil.copytree(fixture_dir, project_dir)

        yae = (yae_root / "yae").as_posix()
        cloned_repositories_arg = f"--cloned_repositories_dir={cloned_repositories_dir}"

        list_result = run([yae, "list", "--plain", cloned_repositories_arg], cwd=project_dir)
        expected_modules = {f"{'self_test_app':30} exe", f"{'self_test_lib':30} lib"}
        listed_modules = {
            line for line in list_result.stdout.splitlines() if not line.startswith("Modules directory:")
        }
        if listed_modules != expected_modules:
            raise RuntimeError(f"Unexpected default list output:\n{list_result.stdout}")
        if not list_result.stdout.startswith("Modules directory: "):
            raise RuntimeError(f"Expected a 'Modules directory:' header line:\n{list_result.stdout}")

        run([yae, "configure", cloned_repositories_arg], cwd=project_dir)
        compile_commands = project_dir / "build" / "compile_commands.json"
        if not compile_commands.is_file():
            raise RuntimeError(f"Expected compilation database at {compile_commands}")
        run([yae, "build", cloned_repositories_arg], cwd=project_dir)

        content_file = project_dir / "build" / "bin" / "content" / "self_test.txt"
        if content_file.read_text(encoding="utf-8").strip() != "content copied":
            raise RuntimeError(f"Expected copied content at {content_file}")

        run_project_dir_env_tests(yae, project_dir, cloned_repositories_dir, Path(temp_dir))
        run_project_discovery_tests(yae, fixture_dir, cloned_repositories_dir, Path(temp_dir))
        run_cloned_repositories_dir_tests(fixture_dir, Path(temp_dir))


def run_project_dir_env_tests(yae: str, project_dir: Path, cloned_repositories_dir: Path, temp_dir: Path) -> None:
    """Verifies that commands work from an unrelated cwd when YAE_PROJECT_DIR points at the project."""

    unrelated_cwd = temp_dir / "unrelated-cwd"
    unrelated_cwd.mkdir(parents=True, exist_ok=True)
    cloned_repositories_arg = f"--cloned_repositories_dir={cloned_repositories_dir}"

    env = os.environ.copy()
    env[PROJECT_DIR_ENV] = project_dir.as_posix()

    result = subprocess.run(
        [yae, "run", cloned_repositories_arg],
        cwd=unrelated_cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Expected 'yae run' to succeed from an unrelated cwd via {PROJECT_DIR_ENV}:\n{result.stdout}"
        )

    bad_target_result = subprocess.run(
        [yae, "run", cloned_repositories_arg, "does-not-exist"],
        cwd=unrelated_cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if bad_target_result.returncode == 0 or "is not an executable module" not in bad_target_result.stdout:
        raise RuntimeError(f"Expected 'yae run does-not-exist' to fail with a clear error:\n{bad_target_result.stdout}")

    # With neither a project nor a cloned repositories root known (regardless of
    # whatever the invoking shell happens to have set), there is nothing to find
    # or discover, so this must fail with a clear error.
    env.pop(PROJECT_DIR_ENV, None)
    env.pop(CLONED_REPOSITORIES_DIR_ENV, None)
    no_project_result = subprocess.run(
        [yae, "list", "--plain"],
        cwd=unrelated_cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if no_project_result.returncode == 0 or "Could not find yae_project.json" not in no_project_result.stdout:
        raise RuntimeError(f"Expected a clear error without a project dir or {PROJECT_DIR_ENV}:\n{no_project_result.stdout}")


def run_project_discovery_tests(yae: str, fixture_dir: Path, cloned_repositories_dir: Path, temp_dir: Path) -> None:
    """Verifies that `yae run <target>` finds a cloned project by scanning
    YAE_CLONED_REPOSITORIES_DIR when no project directory is otherwise known,
    without setting YAE_PROJECT_DIR or passing --project_dir."""

    discoverable_project_dir = cloned_repositories_dir / "yae-self-test-owner" / "discoverable-project" / "main"
    if discoverable_project_dir.exists():
        shutil.rmtree(discoverable_project_dir)
    shutil.copytree(fixture_dir, discoverable_project_dir)

    unrelated_cwd = temp_dir / "discovery-cwd"
    unrelated_cwd.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.pop(PROJECT_DIR_ENV, None)
    env[CLONED_REPOSITORIES_DIR_ENV] = cloned_repositories_dir.as_posix()

    try:
        result = subprocess.run(
            [yae, "run", "self_test_app"],
            cwd=unrelated_cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Expected 'yae run self_test_app' to be discovered via {CLONED_REPOSITORIES_DIR_ENV}:\n{result.stdout}"
            )

        # "self_test_lib" is a library, not an executable, so discovery must not
        # treat it as a runnable target: no candidate project is found at all,
        # and this falls through to the standard "no project" error.
        library_target_result = subprocess.run(
            [yae, "run", "self_test_lib"],
            cwd=unrelated_cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if library_target_result.returncode == 0 or "Could not find yae_project.json" not in library_target_result.stdout:
            raise RuntimeError(
                f"Expected discovery to skip the library module 'self_test_lib':\n{library_target_result.stdout}"
            )

        # Without --all and without a known project, `yae list` must refuse
        # rather than silently aggregating across cloned checkouts.
        no_all_result = subprocess.run(
            [yae, "list", "--plain"],
            cwd=unrelated_cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if no_all_result.returncode == 0 or "pass --all" not in no_all_result.stdout:
            raise RuntimeError(
                f"Expected 'yae list' without --all or a known project to fail clearly:\n{no_all_result.stdout}"
            )

        # `yae list --all` with no project known aggregates modules across every
        # cloned project checkout found under YAE_CLONED_REPOSITORIES_DIR.
        list_result = subprocess.run(
            [yae, "list", "--plain", "--all"],
            cwd=unrelated_cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if list_result.returncode != 0:
            raise RuntimeError(f"Expected aggregate 'yae list --all' to succeed via {CLONED_REPOSITORIES_DIR_ENV}:\n{list_result.stdout}")

        expected_prefix = "yae-self-test-owner/discoverable-project/main"
        expected_lines = {
            f"{'self_test_app':30} {'exe':3} {expected_prefix}/src/self_test_app",
            f"{'self_test_lib':30} {'lib':3} {expected_prefix}/src/self_test_lib",
        }
        listed_lines = set(list_result.stdout.splitlines())
        if not expected_lines.issubset(listed_lines):
            raise RuntimeError(f"Unexpected aggregate list output:\n{list_result.stdout}")
        if not list_result.stdout.startswith(f"Modules directory: {cloned_repositories_dir}"):
            raise RuntimeError(f"Expected a 'Modules directory:' header line:\n{list_result.stdout}")
    finally:
        shutil.rmtree(discoverable_project_dir, ignore_errors=True)


def run_cloned_repositories_dir_tests(fixture_dir: Path, temp_dir: Path) -> None:
    project_dir = temp_dir / "cloned_repositories_dir_project"
    shutil.copytree(fixture_dir, project_dir)

    cli_dir = temp_dir / "cli-repositories"
    local_dir = temp_dir / "local-repositories"
    nested_local_dir = temp_dir / "nested-local-repositories"
    env_dir = temp_dir / "env-repositories"

    with temporary_environment(CLONED_REPOSITORIES_DIR_ENV, None):
        settings = ResolvedSettings.from_project(project_dir)
        if settings.cloned_repositories_dir != project_dir / "cloned_repositories":
            raise RuntimeError(f"Expected project-local default, got {settings.cloned_repositories_dir}")

    with temporary_environment(CLONED_REPOSITORIES_DIR_ENV, env_dir.as_posix()):
        settings = ResolvedSettings.from_project(project_dir)
        if settings.cloned_repositories_dir != env_dir:
            raise RuntimeError(f"Expected environment override, got {settings.cloned_repositories_dir}")

        write_json(project_dir / "local-config.json", {"cloned_repositories_dir": local_dir.as_posix()})
        settings = ResolvedSettings.from_project(project_dir)
        if settings.cloned_repositories_dir != local_dir:
            raise RuntimeError(f"Expected local-config override, got {settings.cloned_repositories_dir}")

        settings = ResolvedSettings.from_project(project_dir, cli_dir)
        if settings.cloned_repositories_dir != cli_dir:
            raise RuntimeError(f"Expected CLI override, got {settings.cloned_repositories_dir}")

        write_json(project_dir / "local-config.json", {"default_configuration": {"cloned_repositories_dir": nested_local_dir.as_posix()}})
        settings = ResolvedSettings.from_project(project_dir)
        if settings.cloned_repositories_dir != nested_local_dir:
            raise RuntimeError(f"Expected nested local-config override, got {settings.cloned_repositories_dir}")

    ctx = GlobalContext(project_root=project_dir, cloned_repositories_dir=env_dir)
    default_cmake_value = CMakePathResolver(ctx).emit_default_cloned_repositories_dir()
    expected_cmake_value = "${CMAKE_CURRENT_SOURCE_DIR}/cloned_repositories"
    if default_cmake_value != expected_cmake_value:
        raise RuntimeError(f"Expected generated CMake default {expected_cmake_value}, got {default_cmake_value}")
