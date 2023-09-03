cmake_minimum_required(VERSION 3.20)
include(set_compiler_options)
set(module_source_files
    ${CMAKE_CURRENT_SOURCE_DIR}/code/private/yae_a.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/yae_a/yae_a.hpp)
add_library(yae_a STATIC ${module_source_files})
set_generic_compiler_options(yae_a PRIVATE)
target_link_libraries(yae_a PUBLIC yae_core)
target_include_directories(yae_a PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/code/public)
target_include_directories(yae_a PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/code/private)
