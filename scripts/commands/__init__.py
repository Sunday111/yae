from commands.build import BuildCommand
from commands.cleanup import CleanupCommand
from commands.configure import ConfigureCommand
from commands.format import FormatCommand
from commands.generate import GenerateCommand
from commands.run import RunCommand


def create_commands():
    return [
        GenerateCommand(),
        ConfigureCommand(),
        BuildCommand(),
        RunCommand(),
        FormatCommand(),
        CleanupCommand(),
    ]
