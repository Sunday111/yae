from __future__ import annotations

import argparse
from pathlib import Path

from yae.cli import execution_list
from yae.cli import log_path
from yae.commands import create_commands
from yae.commands.base import Command
from yae.commands.base import CommandContext


def _plan(command_name: str) -> list[Command]:
    commands_by_name = {command.name: command for command in create_commands()}
    return execution_list(commands_by_name[command_name], commands_by_name)


def _context(project_dir: Path) -> CommandContext:
    return CommandContext.from_args(argparse.Namespace(project_dir=project_dir))


def test_execution_list_puts_dependencies_first() -> None:
    names = [command.name for command in _plan("run")]

    assert names == ["generate", "configure", "build", "run"]


def test_command_that_does_work_is_logged(tmp_path: Path) -> None:
    for name in ("build", "run", "test"):
        assert log_path(_context(tmp_path), _plan(name)) == tmp_path / "yae.log"


# A mistyped --repository_dir names a directory that is not there. Writing a log
# would create it, and the command would then find it inside whichever work tree
# the caller was standing in and use that repository instead of reporting the
# bad path.
def test_command_that_only_reports_is_not_logged(tmp_path: Path) -> None:
    missing = tmp_path / "Sunday111" / "klvk" / "main"

    for name in ("format", "tidy", "list"):
        assert log_path(_context(missing), _plan(name)) is None

    assert not (tmp_path / "Sunday111").exists()
