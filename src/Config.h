#pragma once

#include <cstdint>
#include <cstring>

enum class EmulatedController : std::uint8_t
{
    NintendoSwitchPro = 0
};

inline constexpr const char* emulatedControllerId(EmulatedController controller)
{
    switch (controller)
    {
        case EmulatedController::NintendoSwitchPro:
            return "switch_pro";
    }

    return "switch_pro";
}

inline constexpr const char* emulatedControllerName(EmulatedController controller)
{
    switch (controller)
    {
        case EmulatedController::NintendoSwitchPro:
            return "Nintendo Switch Pro Controller";
    }

    return "Nintendo Switch Pro Controller";
}

inline bool parseEmulatedController(const char* value, EmulatedController& controller)
{
    if (value != nullptr && std::strcmp(value, "switch_pro") == 0)
    {
        controller = EmulatedController::NintendoSwitchPro;
        return true;
    }

    return false;
}

struct Config
{
    char ssid[33]{};
    char password[65]{};
    char hostname[32]{};

    std::uint16_t udpPort = 5454;
    EmulatedController emulatedController = EmulatedController::NintendoSwitchPro;
    bool rumbleEnabled = true;
    std::uint8_t rumbleIntensity = 100; // 0..100 percent
    bool autoWakeEnabled = true;
};
