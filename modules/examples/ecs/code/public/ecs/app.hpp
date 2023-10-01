#pragma once

#include <memory>
#include <unordered_map>
#include <vector>

#include "CppReflection/GetTypeInfo.hpp"
#include "CppReflection/Type.hpp"
#include "EverydayTools/Bitset/DynamicBitset.hpp"
#include "EverydayTools/GUID.hpp"
#include "ankerl/unordered_dense.h"
#include "component_type_id.hpp"
#include "entity_collection.hpp"

namespace ecs
{
class ISystem;
class ComponentPool;

class App
{
public:
    App();
    virtual ~App();

    virtual void RegisterReflectionTypes() = 0;
    virtual void RegisterComponents() = 0;
    virtual void CreateSystems() = 0;
    virtual void Initialize();

    EntityId CreateEntity()
    {
        return entity_collection_.CreateEntity();
    }

    template <typename Component>
    Component& AddComponent(const EntityId entity_id)
    {
        return *reinterpret_cast<Component*>(  // NOLINT
            AddComponent(entity_id, cppreflection::GetTypeInfo<Component>()));
    }

    void* AddComponent(const EntityId entity_id, const cppreflection::Type* type);

    template <typename Component>
    void RemoveComponent(const EntityId entity_id)
    {
        RemoveComponent(entity_id, cppreflection::GetTypeInfo<Component>());
    }

    void RemoveComponent(const EntityId entity_id, const cppreflection::Type* type);

    template <typename Component>
    Component& GetComponent(const EntityId entity_id)
    {
        return *reinterpret_cast<Component*>(  // NOLINT
            GetComponent(entity_id, cppreflection::GetTypeInfo<Component>()));
    }

    void* GetComponent(const EntityId entity_id, const cppreflection::Type* type);

    template <typename Component>
    bool HasComponent(const EntityId entity_id) const
    {
        return HasComponent(entity_id, cppreflection::GetTypeInfo<Component>());
    }

    bool HasComponent(const EntityId entity_id, const cppreflection::Type* type) const;

    bool HasEntity(const EntityId entity_id) const
    {
        return entity_collection_.HasEntity(entity_id);
    }

    void RemoveEntity(const EntityId entity_id);

    using ForEachCallbackRaw = bool (*)(void* user_data, const EntityId entity_id);

    void ForEach(const cppreflection::Type* type, void* user_data, ForEachCallbackRaw callback);
    void ForEach(ComponentPool** pools, const size_t pools_count, void* user_data, ForEachCallbackRaw callback);

    template <typename Callback>
    void ForEach(const cppreflection::Type* type, Callback&& callback)
    {
        ForEach(
            type,
            &callback,
            [](void* user_data, const EntityId entity_id) -> bool
            {
                auto& callback = *reinterpret_cast<Callback*>(user_data);  // NOLINT
                return callback(entity_id);
            });
    }

    template <typename Component, typename Callback>
    void ForEach(Callback&& callback)
    {
        ForEach(cppreflection::GetTypeInfo<Component>(), std::forward<Callback>(callback));
    }

    template <typename Callback, typename... Components>
    void ForEach(std::tuple<Components...>, Callback&& callback)
    {
        constexpr size_t types_count = sizeof...(Components);
        static_assert(types_count != 0);
        if constexpr (types_count == 1)
        {
            ForEach<Components...>(std::forward<Callback>(callback));
        }
        else
        {
            std::array<ComponentPool*, types_count> pools{GetComponentPool<Components>()...};
            ForEach(
                pools.data(),
                types_count,
                &callback,
                [](void* user_data, const EntityId entity_id)
                {
                    auto& callback = *reinterpret_cast<Callback*>(user_data);  // NOLINT
                    return callback(entity_id);
                });
        }
    }

protected:
    void AddSystem(std::unique_ptr<ISystem> system);

    void RegisterComponent(const cppreflection::Type* type);

    template <typename T>
    ComponentPool* GetComponentPool()
    {
        return GetComponentPool(cppreflection::GetTypeInfo<T>());
    }

    ComponentPool* GetComponentPool(const cppreflection::Type* type);

    template <typename T>
    void RegisterComponent()
    {
        RegisterComponent(cppreflection::GetTypeInfo<T>());
    }

private:
    ComponentTypeId MakeComponentTypeId();

private:
    std::vector<std::unique_ptr<ISystem>> systems_;
    ankerl::unordered_dense::map<const cppreflection::Type*, std::unique_ptr<ComponentPool>> components_pools_;
    ankerl::unordered_dense::map<const cppreflection::Type*, ComponentTypeId> components_ids_;
    ComponentTypeId next_component_type_id_ = ComponentTypeId::FromValue(0);
    EntityCollection entity_collection_;
};
}  // namespace ecs
