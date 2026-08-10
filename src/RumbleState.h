#pragma once

#include <cstdint>

struct RumbleState
{
    std::uint8_t raw[8]{};
    std::uint32_t sequence = 0;
    std::uint32_t updatedAtMs = 0;
};
