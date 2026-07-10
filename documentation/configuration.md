# Configuration

Build and configure behavior comes from `default_configuration` in `yae_project.json`, optionally overlaid with
machine-specific settings in `local-config.json`.

## `default_configuration`

Committed project defaults, read by `configure`, `build`, and `run`:

```json
{
    "default_configuration": {
        "build_dir": "build",
        "generator": "Ninja",
        "build_targets": ["verlet_cuda"],
        "run_target": "verlet_cuda",
        "cmake_definitions": {
            "CMAKE_BUILD_TYPE": "Release",
            "CMAKE_CXX_COMPILER": "clang++"
        },
        "environment": {
            "CCACHE_DIR": ".cache/ccache"
        }
    }
}
```

| Key | Used by | Meaning |
| --- | --- | --- |
| `build_dir` | configure, build, run | Build directory (relative paths resolve against the project). Overridable with `--build_dir`. |
| `generator` | configure | CMake generator (`-G`), e.g. `Ninja`. |
| `build_targets` | build | Default targets when `yae build` is given none. |
| `run_target` | run | Default executable for `yae run`. |
| `cmake_definitions` | configure | `-D<name>=<value>` cache definitions. |
| `environment` | configure | Environment variables for the configure process. |

**Value substitution:** `${project_dir}` in a value is replaced with the project's absolute path. Environment values
whose name ends in `_DIR` and that aren't an executable on `PATH` are resolved to a project-relative path and created if
missing (handy for cache directories like `CCACHE_DIR`).

## `local-config.json`

Machine-specific overrides live next to `yae_project.json` in `local-config.json` (which you typically keep
git-ignored). Its contents are merged into `default_configuration`, so you can override just the keys you need:

```json
{
    "cmake_definitions": {
        "CMAKE_C_COMPILER": "/custom/clang"
    }
}
```

You may nest the overrides under a `default_configuration` key or place them at the top level — both are merged. The
cloned-repositories directory can also be set here (`cloned_repositories_dir`); see
[Repositories](repositories.md#resolving-the-cloned-repositories-directory).

## Pinning the support package

By default YAE uses `https://github.com/Sunday111/yae-support main`. Pin a specific ref in `yae_project.json`:

```json
{
    "yae_support": { "link": "https://github.com/Sunday111/yae-support v0.1.0" }
}
```

A plain string is also accepted:

```json
{
    "yae_support": "https://github.com/Sunday111/yae-support v0.1.0"
}
```

See [Generated CMake → the support package](generated-cmake.md#the-support-package) for what it provides.
