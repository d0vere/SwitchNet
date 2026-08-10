#pragma once

#include <Preferences.h>
#include "Config.h"

class Storage
{
public:
    bool begin();
    bool load(Config& cfg);

    // Full save, used when Wi-Fi credentials are explicitly changed.
    bool save(const Config& cfg);

    // Runtime settings save: deliberately leaves SSID/password untouched.
    bool saveRuntimeConfig(const Config& cfg);

    bool scheduleDualUsbLab();
    bool consumeDualUsbLab();
    void clearDualUsbLab();

    void clear();

private:
    Preferences prefs;
    Preferences wifiBackupPrefs;

    bool loadWifiBackup(Config& cfg);
    void saveWifiBackup(const Config& cfg);
};
