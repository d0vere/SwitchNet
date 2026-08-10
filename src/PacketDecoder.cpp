#include "PacketDecoder.h"

#include "Crc32.h"

#include <cstring>

PacketDecoder::Result PacketDecoder::decode(
    const std::uint8_t* data,
    std::size_t size,
    ControllerState& state,
    std::uint32_t& sessionId,
    std::uint32_t& sequence,
    std::uint32_t& clientTimestampUs,
    std::uint8_t& controllerSlot
) const
{
    using namespace SwitchNetProtocol;

    if (data == nullptr || size != CONTROLLER_PACKET_SIZE)
    {
        return Result::InvalidSize;
    }

    ControllerPacket packet{};
    std::memcpy(&packet, data, sizeof(packet));

    if (packet.header.magic != MAGIC)
    {
        return Result::InvalidMagic;
    }

    if (packet.header.version != VERSION)
    {
        return Result::UnsupportedVersion;
    }

    if (packet.header.type != PacketType::ControllerState)
    {
        return Result::UnsupportedType;
    }

    if (
        packet.header.headerSize != HEADER_SIZE ||
        packet.header.payloadSize != CONTROLLER_PAYLOAD_SIZE
    )
    {
        return Result::InvalidLayout;
    }

    if (crc32(data, CRC_INPUT_SIZE) != packet.crc32)
    {
        return Result::InvalidCrc;
    }

    if (packet.state.hat > 8)
    {
        return Result::InvalidState;
    }

    state.buttons = packet.state.buttons;
    state.leftX = packet.state.leftX;
    state.leftY = packet.state.leftY;
    state.rightX = packet.state.rightX;
    state.rightY = packet.state.rightY;
    state.leftTrigger = packet.state.leftTrigger;
    state.rightTrigger = packet.state.rightTrigger;
    state.hat = packet.state.hat;
    state.accelX = packet.state.accelX;
    state.accelY = packet.state.accelY;
    state.accelZ = packet.state.accelZ;
    state.gyroX = packet.state.gyroX;
    state.gyroY = packet.state.gyroY;
    state.gyroZ = packet.state.gyroZ;
    state.imuTimestampUs = packet.state.imuTimestampUs;

    sessionId = packet.header.sessionId;
    sequence = packet.header.sequence;
    clientTimestampUs = packet.header.clientTimestampUs;
    controllerSlot =
        controllerSlotFromFlags(
            packet.header.flags
        );

    if (controllerSlot >= MAX_CONTROLLER_SLOTS)
    {
        return Result::InvalidState;
    }

    return Result::Ok;
}

const char* PacketDecoder::resultName(Result result)
{
    switch (result)
    {
        case Result::Ok: return "ok";
        case Result::InvalidSize: return "invalid_size";
        case Result::InvalidMagic: return "invalid_magic";
        case Result::UnsupportedVersion: return "unsupported_version";
        case Result::UnsupportedType: return "unsupported_type";
        case Result::InvalidLayout: return "invalid_layout";
        case Result::InvalidCrc: return "invalid_crc";
        case Result::InvalidState: return "invalid_state";
    }

    return "unknown";
}

std::uint32_t PacketDecoder::crc32(
    const std::uint8_t* data,
    std::size_t size
)
{
    return SwitchNetCrc32::compute(data, size);
}
