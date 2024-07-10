cmake_minimum_required(VERSION 3.20)

project(YAE_Example)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(YAE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
set(YAE_PROJECT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${YAE_ROOT}/cmake")


# ---------------------------- External Dependencies -----------------------------

