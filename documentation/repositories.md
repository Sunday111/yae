# Repositories & Running From Anywhere

YAE fetches dependencies (and, via `yae clone`, whole projects) into a **cloned-repositories directory**. This document
covers how that directory is resolved, how checkout paths are laid out, and how to drive projects without `cd`-ing into
them.

## Resolving the cloned-repositories directory

YAE resolves the cloned-repositories root in this order:

1. `--cloned_repositories_dir=<path>`
2. `local-config.json` (`cloned_repositories_dir`, top-level or inside `default_configuration`)
3. `YAE_CLONED_REPOSITORIES_DIR` environment variable
4. `${project}/cloned_repositories` (the default)

The default keeps a project self-contained. To share checkouts across projects, set `YAE_CLONED_REPOSITORIES_DIR` (or
`local-config.json`) to a common directory.

## Versioned checkout paths

Every checkout — whether fetched as a dependency or created by `yae clone` — lives at `{owner/repo}/{ref}`, so
different tags/branches of the same repository can coexist under one root and a direct clone shares a directory with a
dependency checkout of the same ref instead of producing a second copy. `https://github.com/Sunday111/klgl main` maps
to `Sunday111/klgl/main`. A ref containing `/` is made path-safe by replacing `/` with `_`. Non-GitHub `GitClone`
modules use their declared `LocalPath` instead.

```bash
yae clone https://github.com/Sunday111/verlet_cuda      # → <root>/Sunday111/verlet_cuda/main
yae clone https://github.com/Sunday111/verlet_cuda v2   # → <root>/Sunday111/verlet_cuda/v2
```

## The registry

YAE records fetched repositories in `registry.json` under the cloned-repositories root. An existing checkout is accepted
and registered when its `origin` URL matches and the requested ref is checked out, points at `HEAD`, or is an ancestor
of `HEAD`. This lets a shared working branch satisfy a pinned base branch without YAE switching your checkout.

`yae git-status` discovers checkouts in the standard versioned layout and also reads this registry for nonstandard
paths — see [Commands](commands.md#yae-git-status).

## Running from anywhere

Normally commands operate on the project in the current directory. Two mechanisms let you work from elsewhere.

### `YAE_PROJECT_DIR`

Point any command at a project without `cd`-ing or passing `--project_dir`:

```bash
YAE_PROJECT_DIR=/path/to/project yae build
```

Resolution order is `--project_dir` → `YAE_PROJECT_DIR` → current directory.

### Discovery by target name

`yae run <target>` and `yae profile <target>` work with **no** project directory at all, as long as
`YAE_CLONED_REPOSITORIES_DIR` points at a directory of cloned project checkouts. YAE searches that directory for a
checkout that declares an executable module named `<target>` and uses it as the project:

```bash
export YAE_CLONED_REPOSITORIES_DIR=/path/to/shared/repositories
yae clone https://github.com/Sunday111/verlet_cuda
cd /anywhere
yae run verlet_cuda
```

This applies only when a target name is given (otherwise there is no project to read a default `run_target` from). If two
cloned projects declare the same executable name, YAE reports the ambiguity and asks you to pass `--project_dir`.

### Listing from anywhere

With no project known, `yae list --all` falls back to `YAE_CLONED_REPOSITORIES_DIR` and lists modules from every cloned
project checkout it finds there, adding a column for the on-disk location. A module shared by several projects (a common
dependency) is listed once, at its real location. Without `--all` in this situation, `list` errors rather than guessing.
See [`yae list`](commands.md#yae-list).
