# YAE

Use the `yae` entrypoint from this repository. It runs through `uv`, which creates a local virtual environment in
`.venv` and stores dependency cache data in `.cache/uv`.

The Python implementation lives under `src/yae`; the root `yae` launcher runs the package entrypoint through `uv`.

## Commands

From a project root:

```bash
yae configure
yae generate
yae build
yae run
yae run some-code-sample
yae list
yae list --all --executables
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

YAE injects `https://github.com/Sunday111/yae-support` as an implicit package dependency. That package provides the
CMake utility modules and built-in example/module declarations used by generated projects, so generated CMake does not
depend on the location of the YAE CLI checkout.

`yae list` shows project modules by default. Use `--support`, `--external`, or `--all` to inspect modules from implicit
support packages and fetched external packages.

Machine-specific overrides can be stored next to `yae_project.json` in `local-config.json`. This file is merged into
`default_configuration`, so either of these forms is valid:

```json
{
    "cmake_definitions": {
        "CMAKE_C_COMPILER": "/custom/clang"
    }
}
```

## Self Test

```bash
uv run --project /path/to/yae python /path/to/yae/tests/run_self_test.py
```

The self-test copies a minimal fixture project to a temporary directory, configures it, builds it, and checks that a
content directory from a library dependency is copied next to the executable.

```json
{
    "default_configuration": {
        "cmake_definitions": {
            "CMAKE_C_COMPILER": "/custom/clang"
        }
    }
}
```
