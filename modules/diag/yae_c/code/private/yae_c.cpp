#include "fmt/format.h"
#include "yae_b/yae_b.hpp"

int main()
{
    yae::module_b::Test test;
    fmt::print("{}\n", test.GetValue());
}
