# Getting Started

This guide takes you from nothing to a built-and-running project.

## Requirements

- **[uv](https://docs.astral.sh/uv/)** on your `PATH`. The `yae` launcher runs the Python tool through `uv`, which
  creates a local virtual environment in `.venv` and caches dependencies in `.cache/uv`. Dependencies are declared in
  `pyproject.toml` and pinned in `uv.lock`; nothing is installed globally.
- **git**, **cmake**, and a working C++ toolchain plus a generator (the example projects use **Ninja**).
- For CUDA projects, the **CUDA toolkit**.

## Installing the `yae` launcher

Clone this repository and use the `yae` script at its root:

```bash
git clone https://github.com/Sunday111/yae
./yae/yae --help
```

For convenience, put it on your `PATH` with a symlink so you can call it as `yae` from anywhere:

```bash
sudo ln -sf "$PWD/yae/yae" /usr/bin/yae
```

The rest of the docs assume `yae` is callable directly.

## Build and run an existing project

If you already have a project checkout (a directory containing `yae_project.json`), run YAE from inside it:

```bash
cd path/to/project
yae build     # clone dependencies, generate CMake, configure, and build
yae run       # (re)build, then run the project's default executable
```

`yae build` runs the whole chain for you — you do not need to run `generate` or `configure` first. See
[Commands](commands.md) for the individual steps and how they depend on each other.

## Clone a project with YAE

`yae clone` fetches a project checkout into your cloned-repositories directory:

```bash
export YAE_CLONED_REPOSITORIES_DIR="$HOME/yae_repositories"
yae clone https://github.com/Sunday111/verlet_cuda
cd "$YAE_CLONED_REPOSITORIES_DIR/Sunday111/verlet_cuda/main"
yae run
```

With `YAE_CLONED_REPOSITORIES_DIR` set you don't even need to `cd`: `yae run verlet_cuda` from any directory finds the
checkout by its target name. See [Repositories & running from anywhere](repositories.md).

## What YAE produces

YAE's job is to **fetch dependencies** and **generate `CMakeLists.txt` files**, which are committed to the project. Once
generated, those files build with plain `cmake` — YAE is not required to configure or build. See
[Generated CMake](generated-cmake.md).

## Next steps

- [Commands](commands.md) — the full command reference.
- [Project model](project-model.md) — how to author `yae_project.json`, packages, and modules.
- [Repositories & running from anywhere](repositories.md) — dependency fetching, path resolution, `YAE_PROJECT_DIR`.
- [Configuration](configuration.md) — `local-config.json`, compiler/generator settings, pinning the support package.
