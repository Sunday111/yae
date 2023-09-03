cmake_minimum_required(VERSION 3.20)
include(set_compiler_options)
set(module_source_files
    ${CMAKE_CURRENT_SOURCE_DIR}/code/private/yae_core.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/yae_core/yae_core.hpp)
add_library(yae_core STATIC ${module_source_files})
set_generic_compiler_options(yae_core PRIVATE)
target_include_directories(yae_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/code/public)
target_include_directories(yae_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/code/private)
