cmake_minimum_required(VERSION 3.20)

project(YAE)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_CURRENT_SOURCE_DIR}/cmake")

set(YAE_ROOT ${CMAKE_CURRENT_SOURCE_DIR})

add_subdirectory(cloned_repositories/fmtlib SYSTEM)
option(INSTALL_GTEST OFF)
option(BUILD_GMOCK OFF)
add_subdirectory(cloned_repositories/gtest SYSTEM)
option(BENCHMARK_ENABLE_TESTING OFF)
add_subdirectory(cloned_repositories/gbench SYSTEM)
add_subdirectory(modules/examples/yae_example_library)
add_subdirectory(modules/examples/yae_example_header_only)
add_subdirectory(modules/examples/yae_example_executable)
add_subdirectory(modules/examples/yae_example_benchmark)
add_subdirectory(modules/examples/yae_example_tests)

enable_testing()
