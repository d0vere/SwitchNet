#pragma once

#include <WiFi.h>
#include <Preferences.h>

#include "Config.h"

class WifiManager
{
public:
    enum class Mode
    {
        Starting,
        AccessPoint,
        StationConnecting,
        StationConnected
    };

    void begin(const Config* config);
    void update();

    bool connected() const;
    bool accessPointActive() const;
    bool everConnected() const;

    Mode mode() const;
    const char* modeName() const;

    std::uint32_t disconnectCount() const;
    std::uint32_t reconnectAttempts() const;
    std::uint32_t recoveryRestarts() const;
    std::uint32_t offlineDurationMs() const;

    void setLowLatencyMode(bool enabled);
    bool lowLatencyMode() const;

private:
    static constexpr std::uint32_t INITIAL_CONNECTION_TIMEOUT_MS = 40000;
    static constexpr std::uint32_t RECONNECT_INTERVAL_MS = 2000;
    static constexpr std::uint32_t STACK_RECOVERY_INTERVAL_MS = 15000;

    Mode mode_ = Mode::Starting;
    Config stationConfig_{};
    bool hasStationConfig_ = false;
    bool everConnected_ = false;
    bool connectionLogged_ = false;
    bool recoveringRuntimeConnection_ = false;
    bool lowLatencyMode_ = false;
    bool setupApRunning_ = false;
    bool wifiPrefsReady_ = false;
    bool credentialsValidated_ = false;
    std::uint32_t credentialFingerprint_ = 0;
    Preferences wifiPrefs_;

    std::uint32_t connectionStartedAt_ = 0;
    std::uint32_t lastReconnectAttemptAt_ = 0;
    std::uint32_t lastStackRecoveryAt_ = 0;
    std::uint32_t disconnectedAt_ = 0;

    std::uint32_t disconnectCount_ = 0;
    std::uint32_t reconnectAttempts_ = 0;
    std::uint32_t recoveryRestarts_ = 0;

    void startStation(const Config& config, bool runtimeRecovery = false);
    void startAccessPoint();
    bool ensureSetupAccessPoint();
    void stopSetupAccessPoint();
    void markConnected();
    void beginRuntimeRecovery();
    void attemptReconnect();
    void recoverWifiStack();

    static std::uint32_t credentialFingerprint(const Config& config);
    void rememberValidatedCredentials();
};
