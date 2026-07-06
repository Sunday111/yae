from yae.commands.build import BuildCommand
from yae.commands.cleanup import CleanupCommand
from yae.commands.configure import ConfigureCommand
from yae.commands.format import FormatCommand
from yae.commands.generate import GenerateCommand
from yae.commands.list import ListCommand
from yae.commands.run import RunCommand


def create_commands():
    return [
        GenerateCommand(),
        ConfigureCommand(),
        BuildCommand(),
        RunCommand(),
        ListCommand(),
        FormatCommand(),
        CleanupCommand(),
    ]
