# Configuration

Build and configure behavior comes from `default_configuration` in `yae_project.json`, optionally overlaid with
machine-specific settings in `local-config.json`.

## `default_configuration`

Committed project defaults, read by `configure`, `build`, `run`, and `profile`:

```json
{
    "default_configuration": {
        "build_dir": "build",
        "build_targets": ["verlet_cuda"],
        "run_target": "verlet_cuda",
        "yae-toolchain": {
            "compiler": "clang",
            "cpplib": "llvm-static"
        },
        "cmake_definitions": {
            "CMAKE_BUILD_TYPE": "Release"
        }
    }
}
```

| Key | Used by | Meaning |
| --- | --- | --- |
| `build_dir` | configure, build, run, profile, tidy | Build directory (relative paths resolve against the project). Overridable with `--build_dir`. |
| `generator` | configure | Optional CMake generator (`-G`); defaults to `Ninja`. |
| `build_targets` | build | Default targets when `yae build` is given none. |
| `run_target` | run, profile | Default executable for `yae run` and `yae profile`. |
| `linker` | configure | Exact linker to use: mold, LLVM LLD, or GNU `ld`. Accepts `mold`, `lld`, or `ld`. |
| `cmake_definitions` | configure | `-D<name>=<value>` cache definitions. |
| `environment` | configure | Environment variables for the configure process. |
| `yae-toolchain` | configure | Optional YAE-generated CMake toolchain; see below. |

YAE enables `CMAKE_EXPORT_COMPILE_COMMANDS` by default. Set it to `OFF` in `cmake_definitions` to disable it.

When `linker` is omitted, YAE selects the first linker available in this order: mold, LLD, then GNU `ld`.
`local-config.json` can override a project's linker like any other default configuration value.

**Value substitution:** `${project_dir}` in a value is replaced with the project's absolute path.

## YAE toolchains

`yae-toolchain` selects a compiler and, optionally, a statically linked C++ standard library:

```json
{
    "yae-toolchain": {
        "compiler": "clang",
        "cpplib": "llvm-static"
    }
}
```

`compiler` accepts `clang` or an exact version such as `clang-22`. For `clang`, YAE first uses an unversioned
`clang`/`clang++` pair. If either is unavailable, it selects the highest installed matching versioned pair.

`cpplib` accepts `llvm-static` for static libc++ and libc++abi, or `gcc-static` for static libstdc++. When omitted,
the compiler's default C++ standard library is used. YAE stores generated toolchain files under
`<cloned_repositories_dir>/.yae/toolchains` and passes the selected file to CMake. Toolchain settings therefore do
not affect committed generated `CMakeLists.txt` files. Adding, removing, or changing `yae-toolchain` requires a fresh
build directory because CMake fixes its toolchain while initializing a build tree.

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
