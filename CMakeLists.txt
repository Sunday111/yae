cmake_minimum_required(VERSION 3.20)

project(YAE)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_CURRENT_SOURCE_DIR}/cmake")

set(YAE_ROOT ${CMAKE_CURRENT_SOURCE_DIR})

# ---------------------------- External Dependencies -----------------------------

# https://github.com/google/benchmark v1.8.3
option(BENCHMARK_ENABLE_TESTING "" OFF)
add_subdirectory(cloned_repositories/google/googlebench/1_8_3 SYSTEM)

# https://github.com/raysan5/raylib 4.5.0
option(BUILD_EXAMPLES "" OFF)
add_subdirectory(cloned_repositories/raylib/4_5_0 SYSTEM)

# https://github.com/fmtlib/fmt 10.1.1
add_subdirectory(cloned_repositories/fmt/10_1_1 SYSTEM)

# https://github.com/Sunday111/EverydayTools for_yae
option(EDT_WITH_TESTS "" ON)
add_subdirectory(cloned_repositories/edt SYSTEM)

# https://github.com/Sunday111/CppReflection for_yae
add_subdirectory(cloned_repositories/CppReflection SYSTEM)

# https://github.com/google/googletest v1.14.0
option(INSTALL_GTEST "" OFF)
option(BUILD_GMOCK "" OFF)
add_subdirectory(cloned_repositories/google/googletest/1_14_0 SYSTEM)

# https://github.com/martinus/unordered_dense v4.1.2
add_subdirectory(cloned_repositories/martinus/unordered_dense SYSTEM)

# --------------------------------- Own Modules ----------------------------------
add_subdirectory(modules/examples/yae_example_library)
add_subdirectory(modules/examples/yae_example_header_only)
add_subdirectory(modules/examples/yae_example_executable)
add_subdirectory(modules/examples/yae_example_tests_main)
add_subdirectory(modules/examples/yae_example_benchmark)
add_subdirectory(modules/examples/yae_example_raylib)
add_subdirectory(modules/examples/ecs)
add_subdirectory(modules/examples/ecs_tests)
add_subdirectory(modules/examples/psr)
add_subdirectory(modules/examples/yae_example_benchmark_main)
add_subdirectory(modules/examples/yae_example_tests)

enable_testing()
