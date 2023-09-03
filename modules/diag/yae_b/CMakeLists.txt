cmake_minimum_required(VERSION 3.20)
include(set_compiler_options)
set(module_source_files
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/yae_b/yae_b.hpp)
add_library(yae_b INTERFACE ${module_source_files})
set_generic_compiler_options(yae_b INTERFACE)
target_link_libraries(yae_b INTERFACE yae_a)
target_include_directories(yae_b INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/code/public)
target_include_directories(yae_b INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/code/private)
