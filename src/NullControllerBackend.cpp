#include "NullControllerBackend.h"

void NullControllerBackend::begin()
{
    reset();
}

void NullControllerBackend::update()
{
}

void NullControllerBackend::setState(const ControllerState& state)
{
    state_ = state;
    ++updates_;
}

void NullControllerBackend::reset()
{
    state_ = ControllerState{};
}

const char* NullControllerBackend::name() const
{
    return "null";
}

bool NullControllerBackend::connected() const
{
    return false;
}


std::uint32_t NullControllerBackend::reportsSent() const
{
    return updates_;
}

std::uint32_t NullControllerBackend::reportsPerSecond() const
{
    return 0;
}

std::uint32_t NullControllerBackend::sendFailures() const
{
    return 0;
}

const ControllerState& NullControllerBackend::state() const
{
    return state_;
}

std::uint32_t NullControllerBackend::updates() const
{
    return updates_;
}
