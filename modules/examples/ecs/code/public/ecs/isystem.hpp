#pragma once

namespace ecs
{

class ISystem
{
public:
    virtual void Tick() = 0;
    virtual ~ISystem() = default;
};

}  // namespace ecs
