# YAE

Use the `yae` entrypoint from this repository.

## Commands

From a project root:

```bash
yae configure
yae generate
yae build
yae run
yae run some-code-sample
yae format
yae cleanup
```

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
including `build_targets`, `run_target`, and `run_copy_target`. `run` uses `run_target` by default; pass a positional
target name to override it.

Machine-specific overrides can be stored next to `yae_project.json` in `local-config.json`. This file is merged into
`default_configuration`, so either of these forms is valid:

```json
{
    "cmake_definitions": {
        "CMAKE_C_COMPILER": "/custom/clang"
    }
}
```

```json
{
    "default_configuration": {
        "cmake_definitions": {
            "CMAKE_C_COMPILER": "/custom/clang"
        }
    }
}
```
