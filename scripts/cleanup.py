import shutil
from typing import Iterable
from pathlib import Path
from global_context import GlobalContext


def main():
    ctx = GlobalContext()

    def dirs_to_remove() -> Iterable[Path]:
        yield ctx.cloned_modules_dir
        yield ctx.root_dir / "build"
        yield ctx.root_dir / ".cache"

    for path in dirs_to_remove():
        shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    main()
