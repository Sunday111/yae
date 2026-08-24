from yae.commands.build import BuildCommand
from yae.commands.cleanup import CleanupCommand
from yae.commands.clone import CloneCommand
from yae.commands.configure import ConfigureCommand
from yae.commands.format import FormatCommand
from yae.commands.generate import GenerateCommand
from yae.commands.git_status import GitStatusCommand
from yae.commands.list import ListCommand
from yae.commands.profile import ProfileCommand
from yae.commands.run import RunCommand
from yae.commands.self_test import SelfTestCommand
from yae.commands.test import TestCommand
from yae.commands.tidy import TidyCommand


def create_commands():
    return [
        CloneCommand(),
        GenerateCommand(),
        ConfigureCommand(),
        BuildCommand(),
        RunCommand(),
        ProfileCommand(),
        TestCommand(),
        ListCommand(),
        GitStatusCommand(),
        FormatCommand(),
        TidyCommand(),
        CleanupCommand(),
        SelfTestCommand(),
    ]
