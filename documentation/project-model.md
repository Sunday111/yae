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
        "generator": "Ninja",
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
| `CopyDirectoriesAfterBuild` | library, executable | Directories copied next to the built binary (e.g. `content`). |
| `ExtraCMakeFiles` | library, executable | Extra `.cmake` files to `include()` for the target. |
| `TargetName` | library, executable | Override the CMake target name (defaults to the module name). |
| `EnableTesting` | library, executable | Enable CTest / GoogleTest discovery for the target. |
| `EnableLTO` | library, executable | Force LTO on/off for this target. |
| `CMakeOptions` | any | CMake `option()`s set before adding the module. |

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
