#pragma once

#include <cstddef>
#include <cstdint>

namespace SwitchNetProtocol
{
    inline constexpr std::uint32_t MAGIC = 0x544E5753U; // "SWNT" little-endian
    inline constexpr std::uint8_t VERSION = 3;

    enum class PacketType : std::uint8_t
    {
        ControllerState = 1,
        Rumble = 2
    };

    enum PacketFlags : std::uint16_t
    {
        None = 0,
        RequestAcknowledgement = 1U << 0,
        ControllerDisconnect = 1U << 1,
        ControllerSlot2 = 1U << 8
    };

    inline constexpr std::uint8_t MAX_CONTROLLER_SLOTS = 2;

    inline constexpr std::uint8_t controllerSlotFromFlags(
        std::uint16_t flags
    )
    {
        return (flags & ControllerSlot2) != 0 ? 1U : 0U;
    }

    inline constexpr std::uint16_t flagsForControllerSlot(
        std::uint8_t slot
    )
    {
        return slot == 1 ? ControllerSlot2 : None;
    }

#pragma pack(push, 1)
    struct WireControllerState
    {
        std::uint32_t buttons;
        std::int16_t leftX;
        std::int16_t leftY;
        std::int16_t rightX;
        std::int16_t rightY;
        std::uint16_t leftTrigger;
        std::uint16_t rightTrigger;
        std::uint8_t hat;
        std::uint8_t reserved[3];
        std::int16_t accelX;
        std::int16_t accelY;
        std::int16_t accelZ;
        std::int16_t gyroX;
        std::int16_t gyroY;
        std::int16_t gyroZ;
        std::uint32_t imuTimestampUs;
    };

    struct PacketHeader
    {
        std::uint32_t magic;
        std::uint8_t version;
        PacketType type;
        std::uint16_t headerSize;
        std::uint16_t payloadSize;
        std::uint16_t flags;
        std::uint32_t sessionId;
        std::uint32_t sequence;
        std::uint32_t clientTimestampUs;
    };

    struct ControllerPacket
    {
        PacketHeader header;
        WireControllerState state;
        std::uint32_t crc32;
    };

    struct WireRumbleState
    {
        std::uint8_t raw[8];
        std::uint16_t holdMs;
        std::uint16_t reserved;
    };

    struct RumblePacket
    {
        PacketHeader header;
        WireRumbleState rumble;
        std::uint32_t crc32;
    };
#pragma pack(pop)

    inline constexpr std::size_t HEADER_SIZE = sizeof(PacketHeader);
    inline constexpr std::size_t CONTROLLER_PAYLOAD_SIZE = sizeof(WireControllerState);
    inline constexpr std::size_t CONTROLLER_PACKET_SIZE = sizeof(ControllerPacket);
    inline constexpr std::size_t RUMBLE_PAYLOAD_SIZE = sizeof(WireRumbleState);
    inline constexpr std::size_t RUMBLE_PACKET_SIZE = sizeof(RumblePacket);
    inline constexpr std::size_t CRC_INPUT_SIZE = offsetof(ControllerPacket, crc32);

    static_assert(HEADER_SIZE == 24, "Unexpected SwitchNet header size");
    static_assert(CONTROLLER_PAYLOAD_SIZE == 36, "Unexpected controller payload size");
    static_assert(CONTROLLER_PACKET_SIZE == 64, "Unexpected SwitchNet packet size");
    static_assert(RUMBLE_PAYLOAD_SIZE == 12, "Unexpected rumble payload size");
    static_assert(RUMBLE_PACKET_SIZE == 40, "Unexpected rumble packet size");
}
