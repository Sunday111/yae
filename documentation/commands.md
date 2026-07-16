# Commands

Run `yae <command> --help` for the exact flags of any command. All commands accept the global flags below.

## Global flags

| Flag | Meaning |
| --- | --- |
| `-v`, `--verbose` | Show verbose diagnostics (and richer log output). |
| `--clone-progress` | Pass `--progress` to `git clone` and stream progress. Useful on slow or unreliable networks. By default clone output is quiet. |

## Where commands look for the project

Every command that operates on a project resolves the project directory in this order:

1. `--project_dir=<path>`
2. `YAE_PROJECT_DIR` environment variable
3. the current working directory

The resolved directory must contain `yae_project.json`. `yae run <target>` can additionally *discover* a project by
target name — see [Repositories & running from anywhere](repositories.md). `yae format` is the exception: it accepts
any directory inside a Git work tree and does not require a YAE project.

The cloned-repositories directory is resolved separately; see
[Repositories](repositories.md#resolving-the-cloned-repositories-directory).

## Command dependencies

Some commands run others first:

```
generate  →  configure  →  build  →  run
```

`configure` runs `generate`, `build` runs `configure`, and `run` runs `build`. So `yae run` from a clean checkout will
fetch dependencies, generate CMake, configure, build, and launch — in one command.

## Reference

### `yae clone <url> [ref]`
Clone a GitHub project checkout into the configured cloned-repositories directory at `{owner/repo}/{ref}` — the same
layout dependency resolution uses, so a direct clone and a dependency checkout of the same ref share one directory.
`ref` defaults to `main`. Flags: `--cloned_repositories_dir`.

### `yae generate`
Generate the committed `CMakeLists.txt` files. Fetches any missing dependencies first. Flags: `--project_dir`,
`--cloned_repositories_dir`.

### `yae configure` (→ generate)
Run CMake configure into the build directory, passing the project's `default_configuration` (generator, cache
definitions, environment) and the resolved `YAE_CLONED_REPOSITORIES_DIR`. Flags: `--project_dir`,
`--cloned_repositories_dir`, `--build_dir`. Extra CMake arguments can be passed after `--`:

```bash
yae configure -- -DCMAKE_BUILD_TYPE=Debug
```

### `yae build [targets...]` (→ configure)
Build CMake targets. With no targets, builds `default_configuration.build_targets` (or the default target set). Flags:
`--project_dir`, `--cloned_repositories_dir`, `--build_dir`.

### `yae run [target] [-- app args...]` (→ build)
Build, then run an executable. Uses `default_configuration.run_target` by default; pass a target name to override.
Arguments after `--` are forwarded to the executable. On systems with NVIDIA PRIME, `run` uses `prime-run` (or the
PRIME environment variables) for discrete-GPU offload. Flags: `--project_dir`, `--cloned_repositories_dir`,
`--build_dir`.

`run` validates the target before building, so an unknown or non-executable target fails with a clear message instead
of a cryptic build error.

### `yae list`
List project modules. See [Project model](project-model.md) for module origins and types.

| Flag | Meaning |
| --- | --- |
| `-e`, `--executables` / `-l`, `--libraries` | Restrict to executables or libraries. |
| `--project` / `--support` / `--external` / `--all` | Restrict to (or include all) module origins. Default is project modules only. |
| `--plain` | Machine-readable rows instead of a table. |

Rows are sorted by name and show the type as `exe`/`lib`; the modules directory is printed above the table. With no
project known, `yae list --all` lists modules across every cloned project under `YAE_CLONED_REPOSITORIES_DIR` (deduped
by on-disk location). See [Repositories](repositories.md#listing-from-anywhere).

### `yae git-status`
Show the git working-tree status of the project checkout and every cloned repository in `registry.json`. By default
only repositories with something to report are shown: working-tree changes (staged, unstaged, or untracked), commits
the upstream branch does not have yet (`N commits not pushed`), or a branch that has no upstream at all. Detached
checkouts (dependencies pinned to tags) and repositories without remotes are not reported as unpushed. `--all` also
lists clean repositories and non-git paths. Works from a project or, with no project known, against
`YAE_CLONED_REPOSITORIES_DIR` alone.

### `yae format`
Apply `clang-format -i` to changed source files. `--all` formats every existing tracked and non-ignored untracked
source, including unmodified files; deleted files remain untouched. `--tool` overrides the `clang-format` executable.
Source suffixes: `.c .cc .cpp .cxx .cu .h .hh .hpp .hxx`.

Unlike project commands, `format` works in any Git work tree without a `yae_project.json`. It resolves the repository
root from the current directory, `--repository_dir`, the backward-compatible `--project_dir` alias, or
`YAE_PROJECT_DIR`; invoking it from a nested directory still formats changes across the whole repository.

### `yae cleanup`
Re-sync git submodules (if any) and then run `git clean -ffdX`. **This deletes all git-ignored files** in the project
(build directories, generated artifacts, etc.), so use it deliberately. Flags: `--project_dir`.

### `yae self-test`
Run YAE's built-in self-test against a bundled fixture project. See [Self test](self-test.md). Flag: `--yae-root`.
