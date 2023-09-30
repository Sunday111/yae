#include <random>

#include "ecs/big_bitset.hpp"
#include "fmt/format.h"
#include "gtest/gtest.h"
#include "test_app.hpp"
#include "test_components.hpp"

TEST(AppTest, StressTest)  // NOLINT
{
    TestApp app;
    app.Initialize();

    std::vector<ecs::EntityId> entities;
    std::vector<const cppreflection::Type*> component_types{
        cppreflection::GetTypeInfo<TestComponentA>(),
        cppreflection::GetTypeInfo<TestComponentB>(),
        cppreflection::GetTypeInfo<TestComponentC>(),
        cppreflection::GetTypeInfo<TestComponentD>()};
    ankerl::unordered_dense::map<ecs::EntityId, ankerl::unordered_dense::set<const cppreflection::Type*>>
        entities_components;
    constexpr unsigned kSeed = 0;
    std::mt19937_64 random_generator(kSeed);  // NOLINT
    std::uniform_int_distribution<size_t> index_distribution;

    auto swap_remove = [&]<typename T>(std::vector<T>& vector, const size_t index)
    {
        const size_t last_index = vector.size() - 1;
        if (index != last_index)
        {
            std::swap(vector[index], vector[last_index]);
        }
        vector.pop_back();
    };

    size_t create_entity_events = 0;
    size_t delete_entity_events = 0;
    size_t add_component_events = 0;
    size_t remove_component_events = 0;

    for (size_t action_index = 0; action_index != 10'000'000; ++action_index)
    {
        const size_t action = entities.empty() ? 0 : index_distribution(random_generator) % 10;

        switch (action)
        {
        case 0:
        case 1:
        case 2:
        {
            // create entity
            ++create_entity_events;
            if (entities.size() < 100'000)
            {
                const ecs::EntityId entity_id = app.CreateEntity();
                ASSERT_TRUE(app.HasEntity(entity_id));
                entities.push_back(entity_id);
            }
            break;
        }
        case 3:
        {
            // delete entity
            ++delete_entity_events;
            if (entities.size() > 0)
            {
                const size_t index = index_distribution(random_generator) % entities.size();
                const ecs::EntityId entity_id = entities[index];
                ASSERT_TRUE(app.HasEntity(entity_id));
                app.RemoveEntity(entity_id);
                ASSERT_FALSE(app.HasEntity(entity_id));

                if (entities_components.contains(entity_id))
                {
                    entities_components.erase(entity_id);
                }

                swap_remove(entities, index);
            }

            break;
        }
        case 4:
        case 5:
        case 6:
        case 7:
        {
            // add component
            ++add_component_events;
            const ecs::EntityId entity_id = entities[index_distribution(random_generator) % entities.size()];
            const size_t component_index = index_distribution(random_generator) % component_types.size();
            const cppreflection::Type* component_type = component_types[component_index];

            auto& entity_components = entities_components[entity_id];
            if (entity_components.contains(component_type))
            {
                ASSERT_TRUE(app.HasComponent(entity_id, component_type));
            }
            else
            {
                ASSERT_FALSE(app.HasComponent(entity_id, component_type));
                app.AddComponent(entity_id, component_type);
                ASSERT_TRUE(app.HasComponent(entity_id, component_type));
                entity_components.insert(component_type);
            }
            break;
        }
        case 8:
        case 9:
        {
            // remove component
            ++remove_component_events;
            const ecs::EntityId entity_id = entities[index_distribution(random_generator) % entities.size()];
            const size_t component_index = index_distribution(random_generator) % component_types.size();
            const cppreflection::Type* component_type = component_types[component_index];
            auto& entity_components = entities_components[entity_id];

            if (entity_components.contains(component_type))
            {
                ASSERT_TRUE(app.HasComponent(entity_id, component_type));
                app.RemoveComponent(entity_id, component_type);
                ASSERT_FALSE(app.HasComponent(entity_id, component_type));
                entity_components.erase(component_type);
            }
            else
            {
                ASSERT_FALSE(app.HasComponent(entity_id, component_type));
            }
            break;
        }
        }
    }

    fmt::print("entities count: {}\n", entities.size());
    fmt::print("\tcreate entity: {}\n", create_entity_events);
    fmt::print("\tdelete entity events: {}\n", delete_entity_events);
    fmt::print("\tadd component events: {}\n", add_component_events);
    fmt::print("\tremove component events: {}\n", remove_component_events);
}

TEST(ComponentPoolTest, ForEach)  // NOLINT
{
    TestApp app;
    app.Initialize();

    std::vector<ecs::EntityId> entities;
    std::vector<const cppreflection::Type*> component_types{
        cppreflection::GetTypeInfo<TestComponentA>(),
        cppreflection::GetTypeInfo<TestComponentB>(),
        cppreflection::GetTypeInfo<TestComponentC>(),
        cppreflection::GetTypeInfo<TestComponentD>()};
    ankerl::unordered_dense::map<ecs::EntityId, ankerl::unordered_dense::set<const cppreflection::Type*>>
        entities_components;
    constexpr unsigned kSeed = 0;
    std::mt19937_64 random_generator(kSeed);  // NOLINT
    std::uniform_int_distribution<size_t> index_distribution;

    auto swap_remove = [&]<typename T>(std::vector<T>& vector, const size_t index)
    {
        const size_t last_index = vector.size() - 1;
        if (index != last_index)
        {
            std::swap(vector[index], vector[last_index]);
        }
        vector.pop_back();
    };

    size_t create_entity_events = 0;
    size_t delete_entity_events = 0;
    size_t add_component_events = 0;
    size_t remove_component_events = 0;

    for (size_t action_index = 0; action_index != 10'000; ++action_index)
    {
        const size_t action = entities.empty() ? 0 : index_distribution(random_generator) % 10;

        switch (action)
        {
        case 0:
        case 1:
        case 2:
        {
            // create entity
            ++create_entity_events;
            if (entities.size() < 100'000)
            {
                const ecs::EntityId entity_id = app.CreateEntity();
                ASSERT_TRUE(app.HasEntity(entity_id));
                entities.push_back(entity_id);
            }
            break;
        }
        case 3:
        {
            // delete entity
            ++delete_entity_events;
            if (entities.size() > 0)
            {
                const size_t index = index_distribution(random_generator) % entities.size();
                const ecs::EntityId entity_id = entities[index];
                ASSERT_TRUE(app.HasEntity(entity_id));
                app.RemoveEntity(entity_id);
                ASSERT_FALSE(app.HasEntity(entity_id));

                if (entities_components.contains(entity_id))
                {
                    entities_components.erase(entity_id);
                }

                swap_remove(entities, index);
            }

            break;
        }
        case 4:
        case 5:
        case 6:
        case 7:
        {
            // add component
            ++add_component_events;
            const ecs::EntityId entity_id = entities[index_distribution(random_generator) % entities.size()];
            const size_t component_index = index_distribution(random_generator) % component_types.size();
            const cppreflection::Type* component_type = component_types[component_index];

            auto& entity_components = entities_components[entity_id];
            if (entity_components.contains(component_type))
            {
                ASSERT_TRUE(app.HasComponent(entity_id, component_type));
            }
            else
            {
                ASSERT_FALSE(app.HasComponent(entity_id, component_type));
                app.AddComponent(entity_id, component_type);
                ASSERT_TRUE(app.HasComponent(entity_id, component_type));
                entity_components.insert(component_type);
            }
            break;
        }
        case 8:
        case 9:
        {
            // remove component
            ++remove_component_events;
            const ecs::EntityId entity_id = entities[index_distribution(random_generator) % entities.size()];
            const size_t component_index = index_distribution(random_generator) % component_types.size();
            const cppreflection::Type* component_type = component_types[component_index];
            auto& entity_components = entities_components[entity_id];

            if (entity_components.contains(component_type))
            {
                ASSERT_TRUE(app.HasComponent(entity_id, component_type));
                app.RemoveComponent(entity_id, component_type);
                ASSERT_FALSE(app.HasComponent(entity_id, component_type));
                entity_components.erase(component_type);
            }
            else
            {
                ASSERT_FALSE(app.HasComponent(entity_id, component_type));
            }
            break;
        }
        }

        std::vector<ecs::EntityId> comp_entities_actual;
        std::vector<ecs::EntityId> comp_entities_expected;
        for (const auto component_type : component_types)
        {
            comp_entities_actual.clear();
            app.ForEach(
                component_type,
                [&](const ecs::EntityId entity_id)
                {
                    comp_entities_actual.push_back(entity_id);
                    return true;
                });

            comp_entities_expected.clear();
            for (const auto entity_id : entities)
            {
                if (entities_components[entity_id].contains(component_type))
                {
                    comp_entities_expected.push_back(entity_id);
                }
            }

            std::ranges::sort(comp_entities_expected, std::less{});
            std::ranges::sort(comp_entities_actual, std::less{});

            ASSERT_EQ(comp_entities_actual, comp_entities_expected);
        }
    }

    fmt::print("entities count: {}\n", entities.size());
    fmt::print("\tcreate entity: {}\n", create_entity_events);
    fmt::print("\tdelete entity events: {}\n", delete_entity_events);
    fmt::print("\tadd component events: {}\n", add_component_events);
    fmt::print("\tremove component events: {}\n", remove_component_events);
}

TEST(AppTest, CreateEntityAddComponent)  // NOLINT
{
    TestApp app;
    app.Initialize();
    const auto entity_id = app.CreateEntity();

    {
        ASSERT_FALSE(app.HasComponent<TestComponentA>(entity_id));
        auto& component = app.AddComponent<TestComponentA>(entity_id);
        component.value = 42;
        ASSERT_TRUE(app.HasComponent<TestComponentA>(entity_id));
    }

    {
        auto& component = app.GetComponent<TestComponentA>(entity_id);
        ASSERT_EQ(component.value, 42);
    }

    app.RemoveComponent<TestComponentA>(entity_id);
    ASSERT_FALSE(app.HasComponent<TestComponentA>(entity_id));
    app.RemoveEntity(entity_id);
    ASSERT_FALSE(app.HasEntity(entity_id));
}
