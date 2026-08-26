# Self Test

```bash
yae self-test
```

The self-test copies a minimal fixture project (`tests/fixtures/minimal_project`) to a temporary directory and exercises
a full slice of YAE end-to-end:

- **`list`** produces the expected project modules.
- **`configure` + `build`** succeed, and a `content` directory from a library dependency is staged next to the built
  executable. Staging is then exercised as it is actually used: a rebuild leaves an unchanged file alone, an edited file
  is re-staged, a file added after configure is staged without configuring again, a deleted source takes its staged copy
  with it, and a file the build never staged is left where it is. See
  [Copying directories after build](project-model.md#copying-directories-after-build).
- **Cloned-repositories-directory precedence** is honored (CLI > `local-config.json` > environment > project default),
  and the generated CMake default for `YAE_CLONED_REPOSITORIES_DIR` is correct.
- **Running from anywhere** works: commands find the project via `YAE_PROJECT_DIR` from an unrelated directory, `yae run`
  discovers a project by target name via `YAE_CLONED_REPOSITORIES_DIR`, and bad/library run targets and missing projects
  fail with clear errors.
- **`list --all`** aggregates modules across cloned projects when no project is otherwise known.

Use `--yae-root` to point at a specific YAE checkout containing `tests/fixtures`.

It builds a real project, so it needs what any generated project needs: CMake 3.29 or newer, a C++ toolchain and
Python 3.12 or newer — see [Getting started](getting-started.md#requirements).

It fetches its dependencies into `.cache/self-test-repositories`, which is reused between runs. The support package is
the exception: it is dropped and fetched again on every run. A [fetched repository](repositories.md#the-registry) is
never updated once it is there, which is what a pinned dependency wants — but the support package ships the CMake and
scripts generated projects build with, and it moves with YAE, so a run that reused an old one would be testing the wrong
thing. Set `YAE_SUPPORT_ROOT` to exercise a specific support checkout instead of fetching it.

## Unit tests

```bash
uv run pytest
```

They live under `tests/` and cover the same building blocks in isolation.
The support package tests its scripts directly; YAE tests the generated interface and exercises the complete pairing in
the self-test above.
