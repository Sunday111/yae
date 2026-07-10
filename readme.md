# YAE

Use the `yae` entrypoint from this repository. It runs through `uv`, which creates a local virtual environment in
`.venv` and stores dependency cache data in `.cache/uv`.

The Python implementation lives under `src/yae`; the root `yae` launcher runs the package entrypoint through `uv`.

## Project Model

A YAE project is a directory with `yae_project.json` and one or more `*.package.json` files. Package files name a
module directory and cloned package dependencies. Module files are `*.module.json` files under the package module
directory; they describe libraries, executables, or git-cloned CMake dependencies.

Generated `CMakeLists.txt` files are committed project files. They must remain usable on another machine without the
YAE Python tool being present. YAE is responsible for generating and fetching, but CMake is responsible for configuring
and building after generation.

## Commands

From a project root:

```bash
yae configure
yae clone https://github.com/Sunday111/verlet_cuda
yae generate
yae build
yae run
yae run some-code-sample
yae list
yae list --all --executables
yae self-test
yae format
yae cleanup
```

`uv` must be available on `PATH`. Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`; they are not
installed globally.

From another directory:

```bash
./yae configure --project_dir=/path/to/project
./yae generate --project_dir=/path/to/project
./yae build --project_dir=/path/to/project
./yae run --project_dir=/path/to/project
./yae run --project_dir=/path/to/project some-code-sample
./yae format --project_dir=/path/to/project
./yae cleanup --project_dir=/path/to/project
```

Commands can depend on other commands. `configure` depends on `generate`, `build` depends on `configure`, and `run`
depends on `build`. Project-specific defaults can be stored in `yae_project.json` under `default_configuration`,
including `build_targets` and `run_target`. `run` uses `run_target` by default; pass a positional target name to
override it.

`yae list` shows project modules by default. Use `--support`, `--external`, or `--all` to inspect modules from implicit
support packages and fetched cloned packages. Use `--plain` when another script needs stable row-oriented output.

Use `--clone-progress` when dependency fetching is slow or the network is unreliable. By default YAE keeps `git clone`
output quiet; with this flag it passes `--progress` to git and streams clone progress.

`yae clone <github-url> [ref]` clones an active project checkout into the configured cloned repositories directory.
Project clones use the plain GitHub repository path so the checkout can be used directly:

```bash
yae clone https://github.com/Sunday111/verlet_cuda
cd "$YAE_CLONED_REPOSITORIES_DIR/Sunday111/verlet_cuda"
yae run
```

The optional `ref` defaults to `main`.

## Generated CMake

YAE injects `https://github.com/Sunday111/yae-support` as an implicit package dependency. That package provides the
CMake utility modules and built-in example/module declarations used by generated projects, so generated CMake does not
depend on the location of the YAE CLI checkout.

Generated CMake exposes cloned repository checkouts as a configurable cache variable:

```cmake
set(YAE_CLONED_REPOSITORIES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cloned_repositories" CACHE PATH "Path to YAE cloned repository checkouts")
```

The default is `cloned_repositories` next to `yae_project.json`. This makes generated CMake self-contained for the
default layout. To build against shared checkouts without invoking YAE, pass the cache variable directly:

```bash
cmake -S . -B build -DYAE_CLONED_REPOSITORIES_DIR=/path/to/shared/repositories
```

`yae configure` also passes this cache variable to CMake using the repository root selected by YAE, so command-line,
local-config, and environment overrides affect configure without changing the committed generated default.

## Repository Checkouts

YAE resolves the cloned repositories root in this order:

1. `--cloned_repositories_dir`
2. `local-config.json`
3. `YAE_CLONED_REPOSITORIES_DIR`
4. `${project}/cloned_repositories`

`local-config.json` may set `cloned_repositories_dir` at the top level or inside `default_configuration`:

```json
{
    "cloned_repositories_dir": "/path/to/shared/repositories"
}
```

```json
{
    "default_configuration": {
        "cloned_repositories_dir": "/path/to/shared/repositories"
    }
}
```

Repository paths for package dependencies and GitHub `GitClone` modules are derived from GitHub links and include the
requested ref, so different tags or branches of the same repository can coexist. For example,
`https://github.com/Sunday111/klgl main` maps to `Sunday111/klgl/main` under the selected repository root. A ref
containing `/` is made path-safe by replacing `/` with `_`. Non-GitHub `GitClone` modules continue to use their
declared `LocalPath`.

YAE records fetched repositories in `registry.json` under the selected repository root. Existing shared checkouts are
accepted and registered when their `origin` URL matches and the requested branch/tag is checked out, points at `HEAD`,
or is an ancestor of `HEAD`. This allows a shared working branch to satisfy a pinned base branch without forcing YAE to
switch the checkout.

Projects can pin the support package ref in `yae_project.json`:

```json
{
    "yae_support": {
        "link": "https://github.com/Sunday111/yae-support v0.1.0"
    }
}
```

Machine-specific configure/build overrides can also be stored next to `yae_project.json` in `local-config.json`. This
file is merged into `default_configuration`:

```json
{
    "cmake_definitions": {
        "CMAKE_C_COMPILER": "/custom/clang"
    }
}
```

## Self Test

```bash
yae self-test
```

The self-test copies a minimal fixture project to a temporary directory, configures it, builds it, and checks that a
content directory from a library dependency is copied next to the executable. It also checks repository-root precedence
and the generated CMake default for `YAE_CLONED_REPOSITORIES_DIR`.
