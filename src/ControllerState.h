#pragma once

#include <cstdint>

enum class ControllerButton : std::uint32_t
{
    A            = 1U << 0,
    B            = 1U << 1,
    X            = 1U << 2,
    Y            = 1U << 3,
    LeftShoulder = 1U << 4,
    RightShoulder= 1U << 5,
    Back         = 1U << 6,
    Start        = 1U << 7,
    LeftStick    = 1U << 8,
    RightStick   = 1U << 9,
    Guide        = 1U << 10,
    Capture      = 1U << 11
};

struct ControllerState
{
    std::uint32_t buttons = 0;

    std::int16_t leftX = 0;
    std::int16_t leftY = 0;
    std::int16_t rightX = 0;
    std::int16_t rightY = 0;

    std::uint16_t leftTrigger = 0;
    std::uint16_t rightTrigger = 0;

    // HID hat: 0..7 directions, 8 neutral.
    std::uint8_t hat = 8;
    std::uint8_t reserved[3]{};

    // IMU already normalized to Nintendo Pro Controller raw units:
    // accelerometer: 4096 counts/g; gyroscope: ~16.384 counts/(deg/s).
    std::int16_t accelX = 0;
    std::int16_t accelY = 0;
    std::int16_t accelZ = 4096;
    std::int16_t gyroX = 0;
    std::int16_t gyroY = 0;
    std::int16_t gyroZ = 0;
    std::uint32_t imuTimestampUs = 0;
};

inline bool isPressed(
    const ControllerState& state,
    ControllerButton button
)
{
    return (state.buttons & static_cast<std::uint32_t>(button)) != 0;
}

static_assert(sizeof(ControllerState) == 36, "Unexpected ControllerState size");
