cmake_minimum_required(VERSION 3.20)
include(set_compiler_options)
set(module_source_files
    ${CMAKE_CURRENT_SOURCE_DIR}/code/private/ecs/app.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/private/ecs/component_pool.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/private/ecs/entity_collection.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/ecs/app.hpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/ecs/component_pool.hpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/ecs/component_type_id.hpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/ecs/constants.hpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/ecs/entity_collection.hpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/ecs/entity_id.hpp
    ${CMAKE_CURRENT_SOURCE_DIR}/code/public/ecs/isystem.hpp)
add_library(ecs STATIC ${module_source_files})
set_generic_compiler_options(ecs PRIVATE)
target_link_libraries(ecs PUBLIC CppReflection
                                 unordered_dense)
target_link_libraries(ecs PRIVATE fmt)
target_include_directories(ecs PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/code/public)
target_include_directories(ecs PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/code/private)
