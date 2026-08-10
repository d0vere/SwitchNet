#pragma once

#include <Arduino.h>
#include <Preferences.h>

#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <BLEAdvertising.h>

#include <cstddef>
#include <cstdint>

class Switch2WakeBoot : public BLEAdvertisedDeviceCallbacks
{
public:
    enum class Action : std::uint8_t
    {
        None = 0,
        Capture = 1,
        Wake = 2
    };

    // Returns true when this boot is an isolated BLE action boot.
    bool begin();
    void update();

    bool scheduleCapture();
    bool requestLiveWake();
    bool clearIdentity();

    bool specialBootActive() const;
    bool identityReady() const;
    const char* identityMac() const;
    const char* lastState() const;
    std::int32_t lastCaptureRssi() const;


    void onResult(BLEAdvertisedDevice advertisedDevice) override;

private:
    static constexpr std::uint16_t NINTENDO_COMPANY_ID = 0x0553;
    static constexpr std::size_t NINTENDO_PAYLOAD_SIZE = 24;
    static constexpr std::size_t WAKE_ADV_SIZE = 31;
    static constexpr std::uint8_t WAKE_FLAG = 0x81;

    static constexpr std::uint32_t CAPTURE_DURATION_SECONDS = 60;
    static constexpr std::uint8_t WAKE_BURSTS = 1;
    static constexpr std::uint32_t WAKE_BURST_MS = 2000;
    static constexpr std::uint32_t WAKE_GAP_MS = 0;
    static constexpr std::uint32_t RESTART_DELAY_MS = 600;

    Preferences prefs_;

    Action action_ = Action::None;
    bool specialBoot_ = false;
    bool liveWakeActive_ = false;
    bool bleInitialized_ = false;

    BLEScan* scan_ = nullptr;
    BLEAdvertising* advertising_ = nullptr;

#if defined(CONFIG_NIMBLE_ENABLED)
    struct ble_gap_adv_params rawAdvParams_{};
#endif

    volatile bool captureFound_ = false;
    std::uint8_t capturedMac_[6] = {};
    std::uint8_t capturedPayload_[NINTENDO_PAYLOAD_SIZE] = {};
    std::int32_t capturedRssi_ = 0;
    std::int32_t lastCaptureRssi_ = 0;

    std::uint8_t savedMac_[6] = {};
    std::uint8_t savedPayload_[NINTENDO_PAYLOAD_SIZE] = {};
    bool identityReady_ = false;
    char identityMacText_[18] = {};

    std::uint8_t wakeAdv_[WAKE_ADV_SIZE] = {};

    std::uint32_t actionStartedAtMs_ = 0;
    std::uint32_t phaseStartedAtMs_ = 0;
    std::uint32_t restartAtMs_ = 0;
    std::uint8_t wakeBurst_ = 0;

    enum class Phase : std::uint8_t
    {
        Idle,
        Capturing,
        Advertising,
        Gap,
        RestartPending
    };

    Phase phase_ = Phase::Idle;
    char state_[96] = "Idle";

    bool loadIdentity();
    bool saveCapturedIdentity();
    bool initializeBle();
    bool beginCapture();
    bool prepareWakeRadio();
    bool startWakeBurst();
    void stopWakeBurst();
    void finishAndRestart(const char* state);
    void finishLiveWake(const char* state);
    void clearPendingAction();

    bool applyCapturedBtMac();
    void buildWakeAdvertisement();

    static bool parseMac(
        const String& text,
        std::uint8_t mac[6]
    );

    void updateMacText();    void setState(const char* state);
};
