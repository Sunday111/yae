cmake_minimum_required(VERSION 3.20)
include(set_compiler_options)
set(module_source_files
    ${CMAKE_CURRENT_SOURCE_DIR}/code/private/yae_core_tests.cpp)
add_executable(yae_core_tests ${module_source_files})
set_generic_compiler_options(yae_core_tests PRIVATE)
target_link_libraries(yae_core_tests PRIVATE gtest
                                             yae_core)
target_include_directories(yae_core_tests PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/code/public)
target_include_directories(yae_core_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/code/private)
