#include "App.h"

#include <Arduino.h>
#include <cstring>

#include "Constants.h"
#include "Version.h"

App::App()
    : udp_(wifi_, backend_, config_),
      autoWake_(udp_, backend_, wake_, config_),
      discovery_(wifi_, config_),
      http_(storage_, wifi_, udp_, backend_, wake_, autoWake_, discovery_, config_)
{
}

void App::begin()
{
    Serial.begin(115200);
    delay(10);

    specialWakeBoot_ = wake_.begin();

    if (specialWakeBoot_)
    {
        Serial.println("[WAKE] Isolated BLE boot mode");
        return;
    }

    Serial.println();
    Serial.println("--------------------------------");
    Serial.print(SWITCHNET_NAME);
    Serial.print(" ");
    Serial.println(SWITCHNET_VERSION);
    Serial.println("--------------------------------");

    const bool storageReady = storage_.begin();

    if (!storageReady)
    {
        Serial.println(
            "[STORAGE] Preferences initialization failed"
        );
    }

    const bool hasConfiguration =
        storageReady && storage_.load(config_);

    if (!hasConfiguration)
    {
        Serial.println("[CONFIG] No saved configuration found");

        std::strncpy(
            config_.hostname,
            HOSTNAME,
            sizeof(config_.hostname) - 1
        );

        config_.hostname[
            sizeof(config_.hostname) - 1
        ] = '\0';

        config_.udpPort = UDP_PORT;
    }
    else
    {
        Serial.println("[CONFIG] Saved configuration loaded");

        Serial.print("[CONFIG] SSID: ");
        Serial.println(config_.ssid);

        Serial.print("[CONFIG] Hostname: ");
        Serial.println(config_.hostname);

        Serial.print("[CONFIG] UDP port: ");
        Serial.println(config_.udpPort);

        Serial.print("[CONFIG] Controller mode: ");
        Serial.println(emulatedControllerName(config_.emulatedController));

        Serial.print("[CONFIG] Rumble: ");
        Serial.println(config_.rumbleEnabled ? "enabled" : "disabled");
    }

    // SwitchNet v1.19 exposes two Nintendo HID interfaces permanently.
    // P2 remains neutral until a controller source claims network slot 2.
    backend_.setDualHidLabEnabled(true);
    backend_.begin();

    Serial.println(
        "[USB] Dynamic dual-controller HID enabled"
    );

    wifi_.begin(hasConfiguration ? &config_ : nullptr);
    udp_.begin(config_.udpPort);
    discovery_.begin();
    http_.begin();
}

void App::update()
{
    if (specialWakeBoot_)
    {
        wake_.update();
        delay(2);
        return;
    }

    wifi_.update();
    wake_.update();

    if (!http_.otaInProgress())
    {
        udp_.update();
        backend_.update();
        autoWake_.update();
        discovery_.update();
    }

    http_.update();
    delay(1);
}
