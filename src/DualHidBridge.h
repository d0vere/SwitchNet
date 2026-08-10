#pragma once

#include <cstddef>
#include <cstdint>

class NintendoProControllerBackend;

class DualHidBridge
{
public:
    static void configure(
        NintendoProControllerBackend* backend,
        bool active
    );

    static bool active();
    static bool ready();
    static bool secondOpen();

    static bool send(
        std::uint8_t reportId,
        const void* data,
        std::uint16_t length
    );

    static std::uint32_t reportsSent();
    static std::uint32_t outputsReceived();
};
