#include "WifiManager.h"

#include <Arduino.h>
#include <cstring>

#include "Constants.h"

void WifiManager::begin(const Config* config)
{
    WiFi.persistent(false);
    WiFi.mode(WIFI_OFF);

    // Keep only a minimal radio-state yield on boot.
    delay(10);

    if (config != nullptr && config->ssid[0] != '\0')
    {
        stationConfig_ = *config;
        hasStationConfig_ = true;

        credentialFingerprint_ =
            credentialFingerprint(stationConfig_);

        wifiPrefsReady_ = wifiPrefs_.begin("snetlink", false);

        if (wifiPrefsReady_)
        {
            credentialsValidated_ =
                wifiPrefs_.getUInt("valid_fp", 0) ==
                credentialFingerprint_;
        }

        startStation(stationConfig_, false);
        return;
    }

    startAccessPoint();
}

void WifiManager::update()
{
    if (mode_ == Mode::StationConnected)
    {
        if (WiFi.status() == WL_CONNECTED)
        {
            return;
        }

        beginRuntimeRecovery();
    }

    if (mode_ != Mode::StationConnecting)
    {
        return;
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        markConnected();
        return;
    }

    const std::uint32_t now = millis();

    /*
     * First connection after boot: if the credentials are incorrect or the
     * router is unavailable, return to the configuration AP after 40 seconds.
     *
     * After SwitchNet has connected successfully at least once, a
     * a temporary network loss must NOT make it abandon the router:
     * keep reconnecting indefinitely.
     */
    if (!recoveringRuntimeConnection_ && !everConnected_)
    {
        if (now - connectionStartedAt_ >= INITIAL_CONNECTION_TIMEOUT_MS)
        {
            Serial.println();
            Serial.println(
                "[WIFI] Initial connection timeout, starting setup access point"
            );

            WiFi.disconnect(false, false);
            startAccessPoint();
        }

        return;
    }

    if (now - lastReconnectAttemptAt_ >= RECONNECT_INTERVAL_MS)
    {
        attemptReconnect();
    }

    if (now - lastStackRecoveryAt_ >= STACK_RECOVERY_INTERVAL_MS)
    {
        recoverWifiStack();
    }
}

bool WifiManager::connected() const
{
    return mode_ == Mode::StationConnected &&
           WiFi.status() == WL_CONNECTED;
}

bool WifiManager::accessPointActive() const
{
    return setupApRunning_;
}

bool WifiManager::everConnected() const
{
    return everConnected_;
}

WifiManager::Mode WifiManager::mode() const
{
    return mode_;
}

const char* WifiManager::modeName() const
{
    switch (mode_)
    {
        case Mode::Starting:
            return "starting";

        case Mode::AccessPoint:
            return "access_point";

        case Mode::StationConnecting:
            return recoveringRuntimeConnection_
                ? "reconnecting"
                : "connecting";

        case Mode::StationConnected:
            return "connected";
    }

    return "unknown";
}

std::uint32_t WifiManager::disconnectCount() const
{
    return disconnectCount_;
}

std::uint32_t WifiManager::reconnectAttempts() const
{
    return reconnectAttempts_;
}

std::uint32_t WifiManager::recoveryRestarts() const
{
    return recoveryRestarts_;
}

std::uint32_t WifiManager::offlineDurationMs() const
{
    if (mode_ != Mode::StationConnecting || disconnectedAt_ == 0)
    {
        return 0;
    }

    return millis() - disconnectedAt_;
}

void WifiManager::setLowLatencyMode(bool enabled)
{
    if (lowLatencyMode_ == enabled)
    {
        return;
    }

    lowLatencyMode_ = enabled;

    if (
        mode_ == Mode::StationConnected ||
        mode_ == Mode::StationConnecting
    )
    {
        WiFi.setSleep(!lowLatencyMode_);
    }
}

bool WifiManager::lowLatencyMode() const
{
    return lowLatencyMode_;
}

void WifiManager::startStation(
    const Config& config,
    bool runtimeRecovery
)
{
    stationConfig_ = config;
    hasStationConfig_ = true;
    recoveringRuntimeConnection_ = runtimeRecovery;

    Serial.print(
        runtimeRecovery
            ? "[WIFI] Recovering connection to "
            : "[WIFI] Validating connection to "
    );
    Serial.println(stationConfig_.ssid);

    mode_ = Mode::StationConnecting;
    connectionStartedAt_ = millis();
    lastReconnectAttemptAt_ = connectionStartedAt_;
    lastStackRecoveryAt_ = connectionStartedAt_;
    connectionLogged_ = false;

    if (runtimeRecovery && disconnectedAt_ == 0)
    {
        disconnectedAt_ = connectionStartedAt_;
    }

    if (
        !runtimeRecovery &&
        !credentialsValidated_
    )
    {
        // Only new or changed credentials need AP+STA provisioning.
        WiFi.mode(WIFI_AP_STA);

        if (!ensureSetupAccessPoint())
        {
            Serial.println(
                "[WIFI] Warning: setup AP could not be started during validation"
            );
        }
    }
    else
    {
        stopSetupAccessPoint();
        WiFi.mode(WIFI_STA);
    }

    const char* hostname =
        stationConfig_.hostname[0] != '\0'
            ? stationConfig_.hostname
            : HOSTNAME;

    WiFi.setHostname(hostname);

    // Never use modem sleep while associating/authenticating. Once the
    // station is connected, markConnected() applies the idle power policy.
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);

    WiFi.begin(
        stationConfig_.ssid,
        stationConfig_.password
    );
}

void WifiManager::markConnected()
{
    mode_ = Mode::StationConnected;
    everConnected_ = true;
    recoveringRuntimeConnection_ = false;
    disconnectedAt_ = 0;
    rememberValidatedCredentials();

    // Provisioning is complete only now. Drop the setup AP after a verified
    // STA connection, then apply the normal idle/low-latency power policy.
    stopSetupAccessPoint();
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(!lowLatencyMode_);

    if (connectionLogged_)
    {
        return;
    }

    connectionLogged_ = true;

    Serial.println();
    Serial.println("[WIFI] Connected to router");

    Serial.print("[WIFI] SSID: ");
    Serial.println(WiFi.SSID());

    Serial.print("[WIFI] IP: ");
    Serial.println(WiFi.localIP());

    Serial.print("[WIFI] RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
}

void WifiManager::beginRuntimeRecovery()
{
    ++disconnectCount_;

    Serial.println("[WIFI] Router connection lost; entering recovery mode");

    mode_ = Mode::StationConnecting;
    recoveringRuntimeConnection_ = true;
    connectionLogged_ = false;
    disconnectedAt_ = millis();
    connectionStartedAt_ = disconnectedAt_;
    lastReconnectAttemptAt_ = 0;
    lastStackRecoveryAt_ = disconnectedAt_;

    attemptReconnect();
}

void WifiManager::attemptReconnect()
{
    if (!hasStationConfig_)
    {
        return;
    }

    lastReconnectAttemptAt_ = millis();
    ++reconnectAttempts_;

    Serial.print("[WIFI] Reconnect attempt #");
    Serial.println(reconnectAttempts_);

    WiFi.reconnect();
}

void WifiManager::recoverWifiStack()
{
    if (!hasStationConfig_)
    {
        return;
    }

    lastStackRecoveryAt_ = millis();
    ++recoveryRestarts_;

    Serial.print("[WIFI] Restarting WiFi station stack, recovery #");
    Serial.println(recoveryRestarts_);

    /*
     * Keep the NVS credentials. Reconfigure only the STA stack
     * to recover from driver states where reconnect() alone is not enough.
     */
    WiFi.disconnect(false, false);
    WiFi.mode(WIFI_OFF);
    delay(50);
    WiFi.mode(WIFI_STA);

    const char* hostname =
        stationConfig_.hostname[0] != '\0'
            ? stationConfig_.hostname
            : HOSTNAME;

    WiFi.setHostname(hostname);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
    WiFi.begin(stationConfig_.ssid, stationConfig_.password);
}

void WifiManager::startAccessPoint()
{
    // Keep STA capability enabled so the setup page can perform Wi-Fi scans.
    WiFi.mode(WIFI_AP_STA);
    WiFi.setSleep(false);

    if (!ensureSetupAccessPoint())
    {
        Serial.println("[WIFI] Failed to start setup access point");
        return;
    }

    mode_ = Mode::AccessPoint;
    recoveringRuntimeConnection_ = false;
    connectionLogged_ = false;

    Serial.println("[WIFI] Setup access point ready");

    Serial.print("[WIFI] SSID: ");
    Serial.println(AP_SSID);

    Serial.print("[WIFI] AP IP: ");
    Serial.println(WiFi.softAPIP());
}

bool WifiManager::ensureSetupAccessPoint()
{
    if (setupApRunning_)
    {
        return true;
    }

    const bool started = WiFi.softAP(AP_SSID);

    if (!started)
    {
        setupApRunning_ = false;
        return false;
    }

    setupApRunning_ = true;
    return true;
}

void WifiManager::stopSetupAccessPoint()
{
    if (!setupApRunning_)
    {
        return;
    }

    WiFi.softAPdisconnect(true);
    setupApRunning_ = false;
}


std::uint32_t WifiManager::credentialFingerprint(const Config& config)
{
    std::uint32_t hash = 2166136261U;

    const auto feed = [&hash](const char* text)
    {
        if (text == nullptr)
        {
            return;
        }

        while (*text != '\0')
        {
            hash ^= static_cast<std::uint8_t>(*text++);
            hash *= 16777619U;
        }

        hash ^= 0xFFU;
        hash *= 16777619U;
    };

    feed(config.ssid);
    feed(config.password);

    return hash == 0 ? 1U : hash;
}

void WifiManager::rememberValidatedCredentials()
{
    credentialsValidated_ = true;

    if (!wifiPrefsReady_)
    {
        wifiPrefsReady_ = wifiPrefs_.begin("snetlink", false);
    }

    if (
        wifiPrefsReady_ &&
        credentialFingerprint_ != 0
    )
    {
        wifiPrefs_.putUInt(
            "valid_fp",
            credentialFingerprint_
        );
    }
}
