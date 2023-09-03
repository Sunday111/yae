cmake_minimum_required(VERSION 3.20)

project(YAE)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_CURRENT_SOURCE_DIR}/cmake")

set(YAE_ROOT ${CMAKE_CURRENT_SOURCE_DIR})

add_subdirectory(cloned_repositories/gtest)
add_subdirectory(cloned_repositories/fmtlib)
add_subdirectory(modules/yae_core)
add_subdirectory(modules/yae_core_tests)
add_subdirectory(modules/diag/yae_a)
add_subdirectory(modules/diag/yae_b)
add_subdirectory(modules/diag/yae_c)
