#include "self_test_lib/value.hpp"

int main()
{
    return self_test_lib::Value() == 42 ? 0 : 1;
}
