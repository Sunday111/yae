#include <random>

#include "ecs/big_bitset.hpp"
#include "fmt/format.h"
#include "gtest/gtest.h"
#include "test_app.hpp"
#include "test_components.hpp"

using A = TestComponentA;
using B = TestComponentB;
using C = TestComponentC;
using D = TestComponentD;

TEST(AppTest, StressTest)  // NOLINT
{
    TestApp app;
    app.Initialize();

    std::vector<ecs::EntityId> entities;
    std::vector<const cppreflection::Type*> component_types{
        cppreflection::GetTypeInfo<A>(),
        cppreflection::GetTypeInfo<B>(),
        cppreflection::GetTypeInfo<C>(),
        cppreflection::GetTypeInfo<D>()};
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
    std::vector<ecs::EntityId> comp_entities_actual;
    std::vector<ecs::EntityId> comp_entities_expected;

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
        ASSERT_FALSE(app.HasComponent<A>(entity_id));
        auto& component = app.AddComponent<A>(entity_id);
        component.value = 42;
        ASSERT_TRUE(app.HasComponent<A>(entity_id));
    }

    {
        auto& component = app.GetComponent<A>(entity_id);
        ASSERT_EQ(component.value, 42);
    }

    app.RemoveComponent<A>(entity_id);
    ASSERT_FALSE(app.HasComponent<A>(entity_id));
    app.RemoveEntity(entity_id);
    ASSERT_FALSE(app.HasEntity(entity_id));
}

TEST(AppTest, ForEachComponent)  // NOLINT
{
    TestApp app;
    app.Initialize();

    const auto e_a = app.CreateEntityWithComponents<A>();
    const auto e_b = app.CreateEntityWithComponents<B>();
    const auto e_c = app.CreateEntityWithComponents<C>();
    const auto e_d = app.CreateEntityWithComponents<D>();
    const auto e_ab = app.CreateEntityWithComponents<A, B>();
    const auto e_bc = app.CreateEntityWithComponents<B, C>();
    const auto e_cd = app.CreateEntityWithComponents<C, D>();
    const auto e_da = app.CreateEntityWithComponents<D, A>();
    const auto e_abc = app.CreateEntityWithComponents<A, B, C>();
    const auto e_bcd = app.CreateEntityWithComponents<B, C, D>();
    const auto e_cda = app.CreateEntityWithComponents<C, D, A>();
    const auto e_dab = app.CreateEntityWithComponents<D, A, B>();
    const auto e_abcd = app.CreateEntityWithComponents<A, B, C, D>();

    auto gather_entities = [&]<typename... Component>(std::tuple<Component...> types)
    {
        std::vector<ecs::EntityId> entities;
        app.ForEach(
            types,
            [&](const ecs::EntityId entity_id)
            {
                entities.push_back(entity_id);
                return true;
            });
        std::ranges::sort(entities, std::less{});
        return entities;
    };

    auto make_vector = [](auto... args)
    {
        std::vector<ecs::EntityId> entities;
        (entities.push_back(args), ...);
        std::ranges::sort(entities, std::less{});
        return entities;
    };

    ASSERT_EQ(gather_entities(std::tuple<A>{}), make_vector(e_a, e_ab, e_da, e_abc, e_cda, e_dab, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<B>{}), make_vector(e_b, e_ab, e_bc, e_abc, e_bcd, e_dab, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<C>{}), make_vector(e_c, e_bc, e_cd, e_abc, e_bcd, e_cda, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<D>{}), make_vector(e_d, e_cd, e_da, e_bcd, e_cda, e_dab, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<A, B>{}), make_vector(e_ab, e_abc, e_dab, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<B, C>{}), make_vector(e_bc, e_abc, e_bcd, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<C, D>{}), make_vector(e_cd, e_bcd, e_cda, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<D, A>{}), make_vector(e_da, e_cda, e_dab, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<A, B, C>{}), make_vector(e_abc, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<B, C, D>{}), make_vector(e_bcd, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<C, D, A>{}), make_vector(e_cda, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<D, A, B>{}), make_vector(e_dab, e_abcd));
    ASSERT_EQ(gather_entities(std::tuple<A, B, C, D>{}), make_vector(e_abcd));
}
