from pathlib import Path
import subprocess

import pytest

from yae.completion import generate_bash_completion


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = Path('/usr/share/bash-completion/bash_completion')


def complete(*words: str, cwd: Path | None = None) -> list[str]:
    if not FRAMEWORK.exists():
        pytest.skip('bash-completion is not installed')
    result = subprocess.run(
        [
            'bash', '--noprofile', '--norc', '-c',
            r'''source "$1"
source "$2"
shift 2
COMP_WORDS=("$@")
COMP_CWORD=$((${#COMP_WORDS[@]} - 1))
COMP_LINE="$*"
COMP_POINT=${#COMP_LINE}
COMP_WORDBREAKS=$' \t\n"\047><=;|&(:'
_yae yae "${COMP_WORDS[COMP_CWORD]}" "${COMP_WORDS[COMP_CWORD-1]}"
((${#COMPREPLY[@]})) && printf '%s\0' "${COMPREPLY[@]}"
exit 0
''',
            'bash', str(FRAMEWORK), str(ROOT / 'completions/yae.bash'), *words,
        ],
        cwd=cwd, capture_output=True, text=True, check=True,
    )
    assert not result.stderr
    return result.stdout.rstrip('\0').split('\0') if result.stdout else []


def test_generated_script_is_current():
    assert (ROOT / 'completions/yae.bash').read_text() == generate_bash_completion()


@pytest.mark.parametrize(('words', 'expected'), [
    (('yae', 'git-'), ['git-status']),
    (('yae', '--verbose', 'git-'), ['git-status']),
    (('yae', 'git-status', '--a'), ['--all']),
    (('yae', 'build', '--b'), ['--build_dir']),
    (('yae', 'profile', '--call-graph', 'd'), ['dwarf']),
    (('yae', 'profile', '--call-graph=d'), ['dwarf']),
    (('yae', 'profile', '--frequency', '--'), []),
    (('yae', 'run', 'example', '--'), []),
    (('yae', 'run', '--', '--'), []),
    (('yae', 'tidy', '--', '--'), []),
    (('yae', 'build', '--project_dir', 'run', '--b'), ['--build_dir']),
    (('yae', 'build', '--project_dir=run', '--b'), ['--build_dir']),
    (('yae', 'build', 'example', '--b'), ['--build_dir']),
])
def test_completion(words, expected):
    assert complete(*words) == expected


@pytest.mark.parametrize('option', ['--project_dir', '--repository_dir'])
def test_directory_completion(tmp_path, option):
    (tmp_path / 'project space').mkdir()
    (tmp_path / 'project_file').touch()
    assert complete('yae', 'format', option, 'proj', cwd=tmp_path) == ['project space']
    assert complete('yae', 'format', option + '=proj', cwd=tmp_path) == ['project space']
