# Self Test

```bash
yae self-test
```

The self-test copies a minimal fixture project (`tests/fixtures/minimal_project`) to a temporary directory and exercises
a full slice of YAE end-to-end:

- **`list`** produces the expected project modules.
- **`configure` + `build`** succeed, and a `content` directory from a library dependency is copied next to the built
  executable.
- **Cloned-repositories-directory precedence** is honored (CLI > `local-config.json` > environment > project default),
  and the generated CMake default for `YAE_CLONED_REPOSITORIES_DIR` is correct.
- **Running from anywhere** works: commands find the project via `YAE_PROJECT_DIR` from an unrelated directory, `yae run`
  discovers a project by target name via `YAE_CLONED_REPOSITORIES_DIR`, and bad/library run targets and missing projects
  fail with clear errors.
- **`list --all`** aggregates modules across cloned projects when no project is otherwise known.

Use `--yae-root` to point at a specific YAE checkout containing `tests/fixtures`.

The unit tests (run with `pytest`) live under `tests/` and cover the same building blocks in isolation.
