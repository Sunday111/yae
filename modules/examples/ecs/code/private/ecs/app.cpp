#include "ecs/app.hpp"

#include "ecs/component_pool.hpp"
#include "ecs/isystem.hpp"

namespace ecs
{

App::App() = default;
App::~App() = default;

void App::AddSystem(std::unique_ptr<ISystem> system)
{
    systems_.push_back(std::move(system));
}

ComponentTypeId App::MakeComponentTypeId()
{
    assert(next_component_type_id_.IsValid());
    const auto result = next_component_type_id_;
    next_component_type_id_ = ComponentTypeId::FromValue(result.GetValue() + 1);
    return result;
}

void App::RegisterComponent(const cppreflection::Type* type)
{
    assert(!components_pools_.contains(type));
    components_pools_[type] = std::make_unique<ComponentPool>(type);

    assert(!components_ids_.contains(type));
    components_ids_[type] = MakeComponentTypeId();
}

void App::Initialize()
{
    RegisterReflectionTypes();
    RegisterComponents();
    CreateSystems();
}

void* App::AddComponent(const EntityId entity_id, const cppreflection::Type* type)
{
    assert(components_pools_.contains(type));
    auto& component_pool = components_pools_[type];

    auto& entity_info = entity_collection_.GetEntityInfo(entity_id);
    assert(!entity_info.components.contains(type));

    const auto component_index = component_pool->Alloc(entity_id);
    auto& component_info = entity_info.components[type];
    component_info.pool_index = component_index;
    component_info.component = component_pool->Get(component_index);

    return component_info.component;
}

void App::RemoveComponent(const EntityId entity_id, const cppreflection::Type* type)
{
    assert(components_pools_.contains(type));
    auto& component_pool = components_pools_[type];

    auto& entity_info = entity_collection_.GetEntityInfo(entity_id);
    assert(entity_info.components.contains(type));

    const auto iterator = entity_info.components.find(type);
    component_pool->Free(iterator->second.pool_index);
    entity_info.components.erase(iterator);
}

void* App::GetComponent(const EntityId entity_id, const cppreflection::Type* type)
{
    assert(components_pools_.contains(type));

    auto& entity_info = entity_collection_.GetEntityInfo(entity_id);
    assert(entity_info.components.contains(type));

    const auto& info = entity_info.components[type];
    return info.component;
}

bool App::HasComponent(const EntityId entity_id, const cppreflection::Type* type) const
{
    assert(components_pools_.contains(type));
    auto& entity_info = entity_collection_.GetEntityInfo(entity_id);
    return entity_info.components.contains(type);
}

void App::RemoveEntity(const EntityId entity_id)
{
    assert(HasEntity(entity_id));
    auto& entity_info = entity_collection_.GetEntityInfo(entity_id);
    for (const auto& [type, component] : entity_info.components)
    {
        RemoveComponent(entity_id, type);
    }
    entity_collection_.DestroyEntity(entity_id);
}

void App::ForEach(const cppreflection::Type* type, void* user_data, ForEachCallbackRaw callback)
{
    assert(components_pools_.contains(type));
    auto& pool_ptr = components_pools_[type];
    pool_ptr->ForEach(user_data, callback);
}
}  // namespace ecs
