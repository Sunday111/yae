cmake_minimum_required(VERSION 3.20)
include(set_compiler_options)
set(module_source_files
    ${CMAKE_CURRENT_SOURCE_DIR}/code/private/yae_c.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/yae_c/yae_c.hpp)
add_executable(yae_c ${module_source_files})
set_generic_compiler_options(yae_c PRIVATE)
target_link_libraries(yae_c PUBLIC yae_b
                                   yae_a
                                   fmt::fmt-header-only)
target_include_directories(yae_c PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/code/public)
target_include_directories(yae_c PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/code/private)
