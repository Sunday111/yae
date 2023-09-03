import shutil
from yae import *


def main():
    ctx = GlobalContext()
    shutil.rmtree(ctx.cloned_modules_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
