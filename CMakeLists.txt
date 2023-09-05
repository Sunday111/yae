cmake_minimum_required(VERSION 3.20)

project(YAE)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_CURRENT_SOURCE_DIR}/cmake")

set(YAE_ROOT ${CMAKE_CURRENT_SOURCE_DIR})

# ---------------------------- External Dependencies -----------------------------

# https://github.com/fmtlib/fmt 10.1.1
add_subdirectory(cloned_repositories/fmtlib SYSTEM)

# https://github.com/google/googletest v1.14.0
option(INSTALL_GTEST OFF)
option(BUILD_GMOCK OFF)
add_subdirectory(cloned_repositories/gtest SYSTEM)

# https://github.com/google/benchmark v1.8.3
option(BENCHMARK_ENABLE_TESTING OFF)
add_subdirectory(cloned_repositories/gbench SYSTEM)

# --------------------------------- Own Modules ----------------------------------
add_subdirectory(modules/examples/yae_example_library)
add_subdirectory(modules/examples/yae_example_header_only)
add_subdirectory(modules/examples/yae_example_executable)
add_subdirectory(modules/examples/yae_example_benchmark)
add_subdirectory(modules/examples/yae_example_tests)

enable_testing()
