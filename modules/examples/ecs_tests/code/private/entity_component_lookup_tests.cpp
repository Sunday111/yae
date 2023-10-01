#include <concepts>
#include <random>

#include "ecs/big_bitset.hpp"
#include "fmt/format.h"
#include "gtest/gtest.h"
#include "test_app.hpp"
#include "test_components.hpp"

TEST(EntityComponentLookupTest, Simple)  // NOLINT
{
    ecs::EntityComponentLookup lookup;

    ASSERT_FALSE(lookup.Has(ecs::EntityId::FromValue(600)));
    lookup.Add(ecs::EntityId::FromValue(600));
    ASSERT_TRUE(lookup.Has(ecs::EntityId::FromValue(600)));

    ASSERT_FALSE(lookup.Has(ecs::EntityId::FromValue(1600)));
    lookup.Add(ecs::EntityId::FromValue(1600));
    ASSERT_TRUE(lookup.Has(ecs::EntityId::FromValue(1600)));

    ASSERT_FALSE(lookup.Has(ecs::EntityId::FromValue(1100)));
    lookup.Add(ecs::EntityId::FromValue(1100));
    ASSERT_TRUE(lookup.Has(ecs::EntityId::FromValue(1100)));

    ASSERT_TRUE(lookup.Has(ecs::EntityId::FromValue(600)));
    lookup.Remove(ecs::EntityId::FromValue(600));
    ASSERT_FALSE(lookup.Has(ecs::EntityId::FromValue(600)));
}

TEST(EntityComponentLookupTest, Fuzzy)  // NOLINT
{
    ecs::EntityComponentLookup lookup;
    std::deque<ecs::EntityId> entities;

    auto next_id = [v = ecs::EntityId{}.GetValue()]() mutable
    {
        ++v;
        if (v == 10'000'000) v = 0;
        return ecs::EntityId::FromValue(v);
    };

    while (entities.size() < 100'000)
    {
        const auto entity_id = next_id();
        entities.push_back(entity_id);
        ASSERT_FALSE(lookup.Has(entity_id));
        lookup.Add(entity_id);
        ASSERT_TRUE(lookup.Has(entity_id));
    }

    for (size_t i = 0; i != 100'000'000; ++i)
    {
        if (i % 1'000'000 == 0)
        {
            fmt::print("{}\n", i / 1'000'000);
        }
        {
            // remove random entity
            const auto entity_id = entities.front();
            entities.pop_front();
            ASSERT_TRUE(lookup.Has(entity_id)) << "i = " << i;
            lookup.Remove(entity_id);
            ASSERT_FALSE(lookup.Has(entity_id)) << "i = " << i;
        }

        {
            // add entity
            const auto entity_id = next_id();
            entities.push_back(entity_id);
            ASSERT_FALSE(lookup.Has(entity_id)) << "i = " << i;
            lookup.Add(entity_id);
            ASSERT_TRUE(lookup.Has(entity_id)) << "i = " << i;
        }
    }
}

template <typename F, typename Ret, typename... Args>
concept Callable = std::invocable<F, Args...> && std::same_as<std::invoke_result_t<F, Args...>, Ret>;

template <Callable<bool, int> Callback>
void ForEachInt(Callback&& callback)
{
    int value = 0;
    while (callback(value))
    {
        ++value;
    }
}
