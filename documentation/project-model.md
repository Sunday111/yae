# Project Model

A YAE project is a directory with a `yae_project.json` file and one or more `*.package.json` files. Packages point at
module directories, and modules (`*.module.json`) describe libraries, executables, or git-cloned CMake dependencies.

Generated `CMakeLists.txt` files are committed project files and must remain usable on another machine without the YAE
tool present. YAE generates and fetches; CMake configures and builds. See [Generated CMake](generated-cmake.md).

## `yae_project.json`

The project root file.

```json
{
    "name": "verlet_cuda",
    "cpp": { "standard": "20" },
    "enable_lto_globally": true,
    "yae_support": { "link": "https://github.com/Sunday111/yae-support main" },
    "default_configuration": {
        "build_dir": "build",
        "build_targets": ["verlet_cuda"],
        "run_target": "verlet_cuda",
        "cmake_definitions": { "CMAKE_BUILD_TYPE": "Release" }
    }
}
```

| Key | Meaning |
| --- | --- |
| `name` | CMake project name. |
| `cpp.standard` | C++ standard (e.g. `"20"`). |
| `enable_lto_globally` | Optional. Enable/disable link-time optimization for the whole project. |
| `yae_support` | Optional. Pin the support package — see [Configuration](configuration.md#pinning-the-support-package). |
| `default_configuration` | Build/configure defaults — see [Configuration](configuration.md). |

## `*.package.json`

A package names a module directory and declares package dependencies (fetched from GitHub).

```json
{
    "modules_dir": "src",
    "dependencies": {
        "packages": [
            { "link": "https://github.com/Sunday111/klgl main", "packages": ["klgl"] }
        ]
    }
}
```

- `modules_dir` — directory (relative to the package file) that is searched recursively for `*.module.json` files.
- `dependencies.packages[].link` — a GitHub link (`<url> [ref]`, `ref` defaults to `main`) providing one or more named
  packages, listed in `packages[]`.

YAE always injects the [`yae-support`](generated-cmake.md#the-support-package) package as an implicit dependency.

## `*.module.json`

A module is a library, executable, or git-cloned dependency. The file name (minus `.module.json`) is the module name.

```json
{
    "ModuleType": "Executable",
    "Dependencies": {
        "Public": ["fmtlib", "edt", "klgl"],
        "Private": []
    },
    "ExtraCMakeFiles": ["add_cuda"],
    "CopyDirectoriesAfterBuild": ["content"]
}
```

### Module types

| `ModuleType` | Meaning |
| --- | --- |
| `Library` | A static library (or an `INTERFACE` library if it has no `.cpp` sources). |
| `Executable` | An executable target. |
| `GitClone` | An external CMake dependency fetched from git and added via `add_subdirectory`. |

### Common fields

| Field | Applies to | Meaning |
| --- | --- | --- |
| `Dependencies.Public` / `Dependencies.Private` | library, executable | Names of modules linked publicly/privately. |
| `CopyDirectoriesAfterBuild` | library, executable | Directories staged next to the built binary (e.g. `content`) — see [below](#copying-directories-after-build). |
| `ExtraCMakeFiles` | library, executable | Extra `.cmake` files to `include()` for the target. |
| `TargetName` | library, executable | Override the CMake target name (defaults to the module name). |
| `EnableTesting` | library, executable | Enable CTest / GoogleTest discovery for the target. |
| `EnableLTO` | library, executable | Force LTO on/off for this target. |
| `CompressDebugInfo` | executable | Compress debug information in the linked executable. Defaults to `true`; prefers zstd and falls back to zlib when supported by the linker. |
| `CMakeOptions` | any | CMake `option()`s set before adding the module. |

### Copying directories after build

Each directory listed in `CopyDirectoriesAfterBuild` is staged next to the built binary, under
`<build>/bin/<directory name>`.

Each module stages its own directories, using `scripts/stage_directories.py` from `yae-support`.
Generated projects therefore need a Python interpreter to build, but not yae.

**Building a target stages what that target needs, and nothing else** — its own content plus the
content of everything it links. A module outside the build does not put its files in the output
directory. (Content staged by an *earlier* build of another target stays where it is; the output
directory is not wiped to match the target you last built.)

Several modules usually stage into the same destination — a library ships its shaders and every
example that uses it ships its own. Each module records what it staged in the build's shared staging
state, which is what lets it remove a file whose source was deleted without touching files another
module staged into the same place. Anything no module staged, including files left there by hand,
is left alone.

Only the source directories are baked into the generated CMake, and they change only when a module
declares a different one. The files themselves are searched at build time, so adding, editing or
deleting one takes effect on the next build with no re-configure.

The generated project reconciles that shared ownership state before staging. It scans every active
source directory first, so moving a destination path from one module to another does not depend on
which target builds first. Files owned by a module no longer in the project are removed, including
when the final staging module disappears. Existing per-module manifests from older generated build
trees are absorbed on the first build. If two active modules provide the same destination path, the
build fails before changing any staged file or manifest. Building only one target does not retire
other modules: every staging module still generated by the project remains an active owner.

Staging compares file contents rather than timestamps. A source restored with an older or unchanged
timestamp is still restaged when its contents differ, and an in-place edit under the build directory
is restored from the declared source on the next build.

### GitClone fields

| Field | Meaning |
| --- | --- |
| `GitUrl` / `GitTag` | Repository URL and ref to fetch. |
| `LocalPath` | Checkout path for non-GitHub URLs. GitHub URLs derive a versioned path automatically — see [Repositories](repositories.md#versioned-checkout-paths). |
| `CMakeFilePath` | Subdirectory containing the dependency's `CMakeLists.txt`, if not at its root. |

Source files under a module directory are discovered by suffix: `.cpp`/`.hpp` (C++) and `.cu` (CUDA). A library with
no `.cpp` files becomes an `INTERFACE` library.

## Module origins

`yae list` groups modules by origin:

- **project** — declared by your project's own packages.
- **support** — provided by the injected `yae-support` package.
- **external** — provided by fetched (cloned) package dependencies.

See [`yae list`](commands.md#yae-list).
