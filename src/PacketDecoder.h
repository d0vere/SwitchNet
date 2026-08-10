#pragma once

#include <cstddef>
#include <cstdint>

#include "ControllerState.h"
#include "SwitchNetProtocol.h"

class PacketDecoder
{
public:
    enum class Result
    {
        Ok,
        InvalidSize,
        InvalidMagic,
        UnsupportedVersion,
        UnsupportedType,
        InvalidLayout,
        InvalidCrc,
        InvalidState
    };

    Result decode(
        const std::uint8_t* data,
        std::size_t size,
        ControllerState& state,
        std::uint32_t& sessionId,
        std::uint32_t& sequence,
        std::uint32_t& clientTimestampUs,
        std::uint8_t& controllerSlot
    ) const;

    static const char* resultName(Result result);
    static std::uint32_t crc32(const std::uint8_t* data, std::size_t size);
};
