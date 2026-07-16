# YAE

YAE clones a C++ project's dependencies and generates its `CMakeLists.txt` files. The generated CMake is committed and
builds with plain `cmake` — **YAE is not required to configure or build**. On top of that, YAE adds convenience commands
(`build`, `run`, `list`, `git-status`, `format`, `tidy`, …) so day-to-day work is a single command.

The Python implementation lives under `src/yae`; the root `yae` launcher runs it through `uv`.

## Requirements

- **[uv](https://docs.astral.sh/uv/)** on your `PATH` (runs YAE in a local `.venv`; nothing is installed globally).
- **git**, **cmake**, **Ninja** (the default generator), and a C++ toolchain.
- **Python 3**, if the project stages content — the build calls a script to do it. Needed to build the
  project even without YAE; see [Generated CMake](documentation/generated-cmake.md#building-without-yae).

## Install

```bash
git clone https://github.com/Sunday111/yae
sudo ln -sf "$PWD/yae/yae" /usr/bin/yae   # optional: call it as `yae` from anywhere
```

## Quick start

**Build and run a project you already have** (a directory containing `yae_project.json`):

```bash
cd path/to/project
yae build     # fetch dependencies, generate CMake, configure, and build
yae run       # (re)build, then run the default executable
```

`yae build` runs the whole `generate → configure → build` chain for you.

**Clone a project with YAE and run it:**

```bash
export YAE_CLONED_REPOSITORIES_DIR="$HOME/yae_repositories"
yae clone https://github.com/Sunday111/verlet_cuda
yae run verlet_cuda          # finds the checkout by target name — no cd needed
```

**See what a project contains:**

```bash
yae list                     # this project's modules
yae git-status               # repos with uncommitted changes
```

## Common flags

- `--project_dir=<path>` or `YAE_PROJECT_DIR` — operate on a project without `cd`-ing into it. For `format`, the path
  may be any Git repository even when it has no `yae_project.json`; `--repository_dir` is a clearer alias.
- `--cloned_repositories_dir=<path>` or `YAE_CLONED_REPOSITORIES_DIR` — where dependencies are fetched/shared.
- `--clone-progress` — stream `git clone` progress on slow networks.

## Building without YAE

Because the CMake files are committed, anyone can build without the tool:

```bash
cmake -S . -B build -DYAE_CLONED_REPOSITORIES_DIR=/path/to/repositories
cmake --build build --parallel
```

See [Generated CMake](documentation/generated-cmake.md) for details.

## Documentation

| Topic | What's in it |
| --- | --- |
| [Getting started](documentation/getting-started.md) | Install, first build, cloning a project. |
| [Commands](documentation/commands.md) | Full reference for every command and its flags. |
| [Project model](documentation/project-model.md) | `yae_project.json`, `*.package.json`, `*.module.json`. |
| [Repositories & running from anywhere](documentation/repositories.md) | Dependency fetching, path resolution, `YAE_PROJECT_DIR`, discovery. |
| [Generated CMake](documentation/generated-cmake.md) | The committed CMake, building without YAE, the support package. |
| [Configuration](documentation/configuration.md) | `local-config.json`, compiler/generator settings, pinning the support package. |
| [Self test](documentation/self-test.md) | What `yae self-test` checks. |
