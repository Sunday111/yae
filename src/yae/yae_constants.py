# File names and layout constants used across YAE and the CMake it generates.

PACKAGE_EXT = ".package.json"
MODULE_EXT = ".module.json"

PROJECT_CONFIG_FILE_NAME = "yae_project.json"
LOCAL_CONFIG_FILE_NAME = "local-config.json"
REGISTRY_FILE_NAME = "registry.json"

CLONED_REPOSITORIES_DIRECTORY_NAME = "cloned_repositories"
DEFAULT_BUILD_DIR_NAME = "build"

# Subdirectories of the CMake build tree. RUNTIME_OUTPUT_SUBDIR is shared by the
# generated CMAKE_RUNTIME_OUTPUT_DIRECTORY and by `yae run` when it locates the
# built executable, so the two cannot drift.
RUNTIME_OUTPUT_SUBDIR = "bin"
ARCHIVE_OUTPUT_SUBDIR = "lib"
GENERATED_MODULES_SUBDIR = "yae_modules"
