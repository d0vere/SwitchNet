#include "Storage.h"

#include <cstring>

bool Storage::begin()
{
    const bool mainReady = prefs.begin("switchnet", false);
    const bool backupReady = wifiBackupPrefs.begin("snetwifi", false);
    return mainReady && backupReady;
}

bool Storage::loadWifiBackup(Config& cfg)
{
    if (!wifiBackupPrefs.isKey("ssid"))
    {
        return false;
    }

    wifiBackupPrefs.getString("ssid", cfg.ssid, sizeof(cfg.ssid));
    wifiBackupPrefs.getString("password", cfg.password, sizeof(cfg.password));
    return cfg.ssid[0] != '\0';
}

void Storage::saveWifiBackup(const Config& cfg)
{
    if (cfg.ssid[0] == '\0')
    {
        return;
    }
    wifiBackupPrefs.putString("ssid", cfg.ssid);
    wifiBackupPrefs.putString("password", cfg.password);
}

bool Storage::load(Config& cfg)
{
    bool haveWifi = false;

    if (prefs.isKey("ssid"))
    {
        prefs.getString("ssid", cfg.ssid, sizeof(cfg.ssid));
        prefs.getString("password", cfg.password, sizeof(cfg.password));
        haveWifi = cfg.ssid[0] != '\0';
    }

    // v1.3.1 keeps a second small namespace for Wi-Fi credentials. This protects
    // credentials from accidental runtime-config writes/clears inside SwitchNet.
    if (!haveWifi && loadWifiBackup(cfg))
    {
        haveWifi = true;
        prefs.putString("ssid", cfg.ssid);
        prefs.putString("password", cfg.password);
    }

    prefs.getString("hostname", cfg.hostname, sizeof(cfg.hostname));
    cfg.udpPort = prefs.getUShort("udp", 5454);
    cfg.rumbleEnabled = prefs.getBool("rumble", true);
    cfg.rumbleIntensity = prefs.getUChar("rumblepct", 100);
    cfg.autoWakeEnabled = prefs.getBool("autowake", true);
    if (cfg.rumbleIntensity > 100)
    {
        cfg.rumbleIntensity = 100;
    }

    const std::uint8_t storedController = prefs.getUChar(
        "ctrlmode",
        static_cast<std::uint8_t>(EmulatedController::NintendoSwitchPro)
    );

    switch (storedController)
    {
        case static_cast<std::uint8_t>(EmulatedController::NintendoSwitchPro):
            cfg.emulatedController = EmulatedController::NintendoSwitchPro;
            break;
        default:
            cfg.emulatedController = EmulatedController::NintendoSwitchPro;
            break;
    }

    if (haveWifi)
    {
        saveWifiBackup(cfg);
    }
    return haveWifi;
}

bool Storage::saveRuntimeConfig(const Config& cfg)
{
    const size_t hostnameWritten = prefs.putString("hostname", cfg.hostname);
    const size_t portWritten = prefs.putUShort("udp", cfg.udpPort);
    const size_t controllerWritten = prefs.putUChar(
        "ctrlmode", static_cast<std::uint8_t>(cfg.emulatedController)
    );
    const size_t rumbleWritten = prefs.putBool("rumble", cfg.rumbleEnabled);
    const size_t intensityWritten = prefs.putUChar("rumblepct", cfg.rumbleIntensity);
    const size_t autoWakeWritten = prefs.putBool("autowake", cfg.autoWakeEnabled);

    return hostnameWritten > 0 &&
           portWritten == sizeof(std::uint16_t) &&
           controllerWritten == sizeof(std::uint8_t) &&
           rumbleWritten == sizeof(bool) &&
           intensityWritten == sizeof(std::uint8_t) &&
           autoWakeWritten == sizeof(bool);
}

bool Storage::save(const Config& cfg)
{
    const size_t ssidWritten = prefs.putString("ssid", cfg.ssid);
    const size_t passwordWritten = prefs.putString("password", cfg.password);
    const bool runtimeSaved = saveRuntimeConfig(cfg);

    if (ssidWritten > 0)
    {
        saveWifiBackup(cfg);
    }

    return ssidWritten > 0 && runtimeSaved &&
           (cfg.password[0] == '\0' || passwordWritten > 0);
}

bool Storage::scheduleDualUsbLab()
{
    return prefs.putBool("duallab", true) == sizeof(bool);
}

bool Storage::consumeDualUsbLab()
{
    const bool enabled =
        prefs.getBool("duallab", false);

    // One-shot safety: consume BEFORE USB initialization. Any reset after
    // this point returns to the stable single-controller descriptor.
    if (enabled)
    {
        prefs.remove("duallab");
    }

    return enabled;
}

void Storage::clearDualUsbLab()
{
    prefs.remove("duallab");
}

void Storage::clear()
{
    prefs.clear();
    wifiBackupPrefs.clear();
}
