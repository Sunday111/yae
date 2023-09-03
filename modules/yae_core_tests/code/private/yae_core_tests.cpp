#include "gtest/gtest.h"
#include "yae_core/yae_core.hpp"

TEST(FooTest, DoesXyz) {}

int main(int argc, char** argv)
{
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
