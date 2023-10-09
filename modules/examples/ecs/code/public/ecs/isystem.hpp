#pragma once

namespace ecs
{

class App;

class ISystem
{
public:
    virtual void Tick(App& app) = 0;
    virtual ~ISystem() = default;
};

}  // namespace ecs
