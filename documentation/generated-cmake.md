# Generated CMake

YAE generates `CMakeLists.txt` files that are **committed** to the project. They must remain usable on another machine
without the YAE tool present: YAE is responsible for generating and fetching, CMake for configuring and building.

## Building without YAE

Once the CMake files and dependencies are in place, configure and build with plain CMake:

```bash
cmake -S . -B build
cmake --build build --parallel
```

Generated CMake exposes the cloned-repositories root as a cache variable:

```cmake
set(YAE_CLONED_REPOSITORIES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cloned_repositories"
    CACHE PATH "Path to YAE cloned repository checkouts")
```

The default is `cloned_repositories` next to `yae_project.json`, which makes the generated CMake self-contained for the
default layout. To build against shared checkouts without invoking YAE, pass the cache variable directly:

```bash
cmake -S . -B build -DYAE_CLONED_REPOSITORIES_DIR=/path/to/shared/repositories
```

`yae configure` passes this cache variable using the root [resolved by YAE](repositories.md#resolving-the-cloned-repositories-directory),
so command-line, `local-config.json`, and environment overrides affect configure without changing the committed default.

## The support package

YAE injects `https://github.com/Sunday111/yae-support` as an implicit package dependency. It provides the CMake utility
modules and built-in example/module declarations that generated projects rely on, so the generated CMake does not depend
on the location of the YAE CLI checkout. The generated root sets `YAE_SUPPORT_ROOT` and adds its `cmake/` directory to
`CMAKE_MODULE_PATH`.

Pin the support package ref in `yae_project.json` — see
[Configuration](configuration.md#pinning-the-support-package).

## Layout of generated output

- Runtime binaries are written to `<build>/bin`, archives/libraries to `<build>/lib`.
- Each fetched module is added under `<build>/yae_modules/<path>` as a CMake subdirectory.
- `CopyDirectoriesAfterBuild` entries (e.g. `content`) are staged next to the executable by a
  `<target>_copy_files` target per module, so a build stages what it needs and no more. See
  [Copying directories after build](project-model.md#copying-directories-after-build).

Regenerate the files with [`yae generate`](commands.md#yae-generate) whenever you add or change modules.
