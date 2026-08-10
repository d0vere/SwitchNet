#pragma once

#include <cstdint>

#include "IControllerBackend.h"

class NullControllerBackend final : public IControllerBackend
{
public:
    void begin() override;
    void update() override;
    void setState(const ControllerState& state) override;
    void reset() override;

    const char* name() const override;
    bool connected() const override;

    std::uint32_t reportsSent() const override;
    std::uint32_t reportsPerSecond() const override;
    std::uint32_t sendFailures() const override;

    const ControllerState& state() const;
    std::uint32_t updates() const;

private:
    ControllerState state_{};
    std::uint32_t updates_ = 0;
};
