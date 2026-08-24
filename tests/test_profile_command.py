from __future__ import annotations

from pathlib import Path
import argparse
import json

import pytest

from yae.cli import create_parser
from yae.cli import execution_list
from yae.commands import create_commands
from yae.commands import profile as profile_module
from yae.commands.base import CommandContext
from yae.commands.profile import ProfileCommand
from yae.commands.run import RunCommand
from yae.errors import ProjectError


def project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "yae_project.json").write_text(
        json.dumps({"default_configuration": {"run_target": "app"}}),
        encoding="utf-8",
    )
    return project_dir


def arguments(output: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "app_args": ["--example", "value"],
        "call_graph": "fp",
        "event": "cycles:u",
        "frequency": 999,
        "output": output,
        "overwrite": False,
        "perf": "perf",
        "run_target": "app",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def context(project_dir: Path, build_dir: Path | None = None) -> CommandContext:
    return CommandContext.from_args(
        argparse.Namespace(
            build_dir=build_dir,
            clone_progress=False,
            cloned_repositories_dir=None,
            project_dir=project_dir,
        )
    )


def test_profile_command_uses_build_pipeline_and_project_configuration() -> None:
    commands = create_commands()
    commands_by_name = {command.name: command for command in commands}
    parser = create_parser(commands)

    args = parser.parse_args(["profile", "--output", "/tmp/profile", "app", "--", "--example"])
    plan = execution_list(commands_by_name["profile"], commands_by_name)
    profile_command = commands_by_name["profile"]
    assert isinstance(profile_command, ProfileCommand)
    profile_command._normalize_target_and_app_arguments(args)

    assert [command.name for command in plan] == ["generate", "configure", "build", "profile"]
    assert args.run_target == "app"
    assert args.app_args == ["--example"]
    assert not hasattr(args, "cmake_args")


def test_profile_command_accepts_app_arguments_with_default_target() -> None:
    commands = create_commands()
    commands_by_name = {command.name: command for command in commands}
    parser = create_parser(commands)

    args = parser.parse_args(["profile", "--output", "/tmp/profile", "--", "--example"])
    profile_command = commands_by_name["profile"]
    assert isinstance(profile_command, ProfileCommand)
    profile_command._normalize_target_and_app_arguments(args)

    assert args.run_target is None
    assert args.app_args == ["--example"]


def test_profile_records_and_exports_target(tmp_path: Path, monkeypatch) -> None:
    project_dir = project(tmp_path)
    output = tmp_path / "profile"
    build_dir = output / "build"
    calls: list[tuple[list[str], Path | None, dict[str, str] | None, str | None]] = []

    def capture(command, cwd=None, env=None, stdout=None) -> None:  # noqa: ANN001
        calls.append((list(command), cwd, env, getattr(stdout, "name", None)))

    monkeypatch.setattr(profile_module, "run_subprocess", capture)
    monkeypatch.setattr(profile_module.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        profile_module,
        "command_with_discrete_gpu",
        lambda command: (["prime-run", *command], {"PROFILE_TEST": "1"}),
    )

    ProfileCommand().run(context(project_dir, build_dir), arguments(output))

    application = build_dir / "bin" / "app"
    perf_data = output / "perf.data"
    speedscope_profile = output / "profile.linux-perf.txt"
    assert calls == [
        (
            [
                "/usr/bin/perf",
                "record",
                "--output",
                perf_data.as_posix(),
                "--event",
                "cycles:u",
                "--freq",
                "999",
                "--call-graph",
                "fp",
                "--",
                "prime-run",
                application.as_posix(),
                "--example",
                "value",
            ],
            None,
            {"PROFILE_TEST": "1"},
            None,
        ),
        (
            [
                "/usr/bin/perf",
                "script",
                "--input",
                perf_data.as_posix(),
            ],
            None,
            None,
            speedscope_profile.as_posix(),
        ),
    ]


def test_profile_validation_uses_output_build_directory(tmp_path: Path, monkeypatch) -> None:
    project_dir = project(tmp_path)
    output = tmp_path / "profile"
    command_context = context(project_dir)
    monkeypatch.setattr(RunCommand, "validate", lambda self, command_context, args: None)
    monkeypatch.setattr(profile_module.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    ProfileCommand().validate(command_context, arguments(output))

    assert command_context.build_dir_override == output / "build"


def test_profile_validation_preserves_existing_files(tmp_path: Path, monkeypatch) -> None:
    project_dir = project(tmp_path)
    output = tmp_path / "profile"
    output.mkdir()
    (output / "perf.data").write_text("existing", encoding="utf-8")
    monkeypatch.setattr(RunCommand, "validate", lambda self, command_context, args: None)
    monkeypatch.setattr(profile_module.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    with pytest.raises(ProjectError, match="pass --overwrite"):
        ProfileCommand().validate(context(project_dir), arguments(output))


def test_profile_validation_rejects_output_file(tmp_path: Path, monkeypatch) -> None:
    project_dir = project(tmp_path)
    output = tmp_path / "profile"
    output.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(RunCommand, "validate", lambda self, command_context, args: None)
    monkeypatch.setattr(profile_module.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    with pytest.raises(ProjectError, match="is not a directory"):
        ProfileCommand().validate(context(project_dir), arguments(output))
