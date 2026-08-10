#include "Switch2WakeBoot.h"

#include <cstring>
#include <cstdio>

#include "esp_err.h"
#include "esp_mac.h"

bool Switch2WakeBoot::begin()
{
    if (!prefs_.begin("snetwake", false))
    {
        setState("Wake storage unavailable");
        return false;
    }

    identityReady_ = loadIdentity();

    const std::uint8_t rawAction =
        prefs_.getUChar("action", static_cast<std::uint8_t>(Action::None));

    action_ = static_cast<Action>(rawAction);

    if (action_ == Action::None)
    {
        specialBoot_ = false;
        setState(identityReady_ ? "Wake identity ready" : "No wake identity captured");
        return false;
    }

    specialBoot_ = true;
    actionStartedAtMs_ = millis();

    if (action_ == Action::Capture)
    {
        if (!beginCapture())
        {
            finishAndRestart("BLE capture failed");
        }
    }
    else if (action_ == Action::Wake)
    {
        // Compatibility with a pending action left by an older firmware.
        // Wake is live in v1.15+, so return to normal mode instead of entering
        // an isolated BLE boot.
        clearPendingAction();
        specialBoot_ = false;
        action_ = Action::None;
        setState(identityReady_ ? "Wake identity ready" : "No wake identity captured");
        return false;
    }
    else
    {
        finishAndRestart("Unknown wake action");
    }

    return true;
}

void Switch2WakeBoot::update()
{
    if (!specialBoot_ && !liveWakeActive_)
    {
        return;
    }

    const std::uint32_t now = millis();

    if (specialBoot_ && phase_ == Phase::Capturing)
    {
        if (captureFound_)
        {
            if (scan_ != nullptr && scan_->isScanning())
            {
                scan_->stop();
            }

            if (saveCapturedIdentity())
            {
                finishAndRestart("Nintendo wake identity captured");
            }
            else
            {
                finishAndRestart("Failed to save wake identity");
            }
            return;
        }

        if (
            now - actionStartedAtMs_ >=
            CAPTURE_DURATION_SECONDS * 1000U
        )
        {
            if (scan_ != nullptr && scan_->isScanning())
            {
                scan_->stop();
            }
            finishAndRestart("Capture timed out");
            return;
        }
    }
    else if (phase_ == Phase::Advertising)
    {
        if (now - phaseStartedAtMs_ >= WAKE_BURST_MS)
        {
            stopWakeBurst();
        }
    }
    else if (phase_ == Phase::Gap)
    {
        if (now - phaseStartedAtMs_ >= WAKE_GAP_MS)
        {
            if (!startWakeBurst())
            {
                finishAndRestart("BLE wake burst failed");
            }
        }
    }
    else if (phase_ == Phase::RestartPending)
    {
        if (
            static_cast<std::int32_t>(now - restartAtMs_) >= 0
        )
        {
            ESP.restart();
        }
    }
}

bool Switch2WakeBoot::scheduleCapture()
{
    if (!prefs_.isKey("action") && !prefs_.putUChar(
        "action",
        static_cast<std::uint8_t>(Action::Capture)
    ))
    {
        return false;
    }

    if (
        prefs_.putUChar(
            "action",
            static_cast<std::uint8_t>(Action::Capture)
        ) != sizeof(std::uint8_t)
    )
    {
        return false;
    }

    setState("Capture scheduled");
    return true;
}

bool Switch2WakeBoot::requestLiveWake()
{
    if (!identityReady_)
    {
        setState("No wake identity captured");
        return false;
    }

    if (specialBoot_ || liveWakeActive_ || phase_ != Phase::Idle)
    {
        setState("Wake radio is busy");
        return false;
    }

    liveWakeActive_ = true;

    if (!prepareWakeRadio())
    {
        liveWakeActive_ = false;
        phase_ = Phase::Idle;
        return false;
    }

    return true;
}


bool Switch2WakeBoot::clearIdentity()
{
    const bool macOk = prefs_.remove("mac");
    const bool payloadOk = prefs_.remove("payload");
    prefs_.remove("rssi");
    prefs_.remove("action");

    identityReady_ = false;
    lastCaptureRssi_ = 0;
    std::memset(savedMac_, 0, sizeof(savedMac_));
    std::memset(savedPayload_, 0, sizeof(savedPayload_));
    identityMacText_[0] = '\0';

    setState("Wake identity cleared");
    return macOk || payloadOk;
}

bool Switch2WakeBoot::specialBootActive() const
{
    return specialBoot_;
}

bool Switch2WakeBoot::identityReady() const
{
    return identityReady_;
}

const char* Switch2WakeBoot::identityMac() const
{
    return identityMacText_;
}

const char* Switch2WakeBoot::lastState() const
{
    return state_;
}

std::int32_t Switch2WakeBoot::lastCaptureRssi() const
{
    return lastCaptureRssi_;
}


void Switch2WakeBoot::onResult(
    BLEAdvertisedDevice advertisedDevice
)
{
    if (
        phase_ != Phase::Capturing ||
        captureFound_ ||
        !advertisedDevice.haveManufacturerData()
    )
    {
        return;
    }

    const String manufacturer =
        advertisedDevice.getManufacturerData();

    // Arduino BLE returns company ID + manufacturer-specific bytes.
    if (
        manufacturer.length() != NINTENDO_PAYLOAD_SIZE + 2 ||
        static_cast<std::uint8_t>(manufacturer[0]) != 0x53 ||
        static_cast<std::uint8_t>(manufacturer[1]) != 0x05
    )
    {
        return;
    }

    std::uint8_t mac[6] = {};
    if (!parseMac(advertisedDevice.getAddress().toString(), mac))
    {
        return;
    }

    std::memcpy(capturedMac_, mac, sizeof(capturedMac_));
    std::memcpy(
        capturedPayload_,
        manufacturer.c_str() + 2,
        sizeof(capturedPayload_)
    );
    capturedRssi_ = advertisedDevice.getRSSI();

    captureFound_ = true;
}

bool Switch2WakeBoot::loadIdentity()
{
    if (
        prefs_.getBytesLength("mac") != sizeof(savedMac_) ||
        prefs_.getBytesLength("payload") != sizeof(savedPayload_)
    )
    {
        return false;
    }

    if (
        prefs_.getBytes("mac", savedMac_, sizeof(savedMac_)) !=
            sizeof(savedMac_) ||
        prefs_.getBytes(
            "payload",
            savedPayload_,
            sizeof(savedPayload_)
        ) != sizeof(savedPayload_)
    )
    {
        return false;
    }

    lastCaptureRssi_ = prefs_.getInt("rssi", 0);
    updateMacText();
    return true;
}

bool Switch2WakeBoot::saveCapturedIdentity()
{
    const std::size_t macWritten =
        prefs_.putBytes("mac", capturedMac_, sizeof(capturedMac_));

    const std::size_t payloadWritten =
        prefs_.putBytes(
            "payload",
            capturedPayload_,
            sizeof(capturedPayload_)
        );

    prefs_.putInt("rssi", capturedRssi_);
    lastCaptureRssi_ = capturedRssi_;

    return
        macWritten == sizeof(capturedMac_) &&
        payloadWritten == sizeof(capturedPayload_);
}

bool Switch2WakeBoot::initializeBle()
{
    if (bleInitialized_)
    {
        return true;
    }

    if (!BLEDevice::init("SwitchNet Wake"))
    {
        setState("BLE initialization failed");
        return false;
    }

    bleInitialized_ = true;
    return true;
}

bool Switch2WakeBoot::beginCapture()
{
    clearPendingAction();

    if (!initializeBle())
    {
        return false;
    }

    scan_ = BLEDevice::getScan();
    if (scan_ == nullptr)
    {
        setState("BLE scanner unavailable");
        return false;
    }

    // Active scanning maximizes the chance of receiving controller data that
    // may be exposed in a scan response.
    scan_->setActiveScan(true);
    scan_->setInterval(320);
    scan_->setWindow(30);
    scan_->setAdvertisedDeviceCallbacks(this, true, true);

    captureFound_ = false;
    actionStartedAtMs_ = millis();
    phase_ = Phase::Capturing;
    setState("Capturing Nintendo BLE identity");

    return scan_->start(
        CAPTURE_DURATION_SECONDS,
        nullptr,
        false
    );
}

bool Switch2WakeBoot::prepareWakeRadio()
{
    if (!identityReady_)
    {
        setState("No wake identity captured");
        return false;
    }

    if (!bleInitialized_)
    {
        if (
            esp_iface_mac_addr_set(
                savedMac_,
                ESP_MAC_BT
            ) != ESP_OK
        )
        {
            setState("Bluetooth MAC spoof failed");
            return false;
        }

        if (!initializeBle())
        {
            return false;
        }
    }

#if defined(CONFIG_NIMBLE_ENABLED)
    // Keep the safety check that proved critical during wake development:
    // the address NimBLE will advertise must match the captured controller.
    std::uint8_t nimbleOwn[6] = {};

    if (
        ble_hs_id_copy_addr(
            BLE_ADDR_PUBLIC,
            nimbleOwn,
            nullptr
        ) != 0
    )
    {
        setState("Unable to read NimBLE public MAC");
        return false;
    }

    for (std::size_t i = 0; i < 6; ++i)
    {
        if (nimbleOwn[5 - i] != savedMac_[i])
        {
            setState("NimBLE public MAC mismatch");
            return false;
        }
    }

    buildWakeAdvertisement();

    std::memset(
        &rawAdvParams_,
        0,
        sizeof(rawAdvParams_)
    );
    rawAdvParams_.conn_mode = BLE_GAP_CONN_MODE_NON;
    rawAdvParams_.disc_mode = BLE_GAP_DISC_MODE_GEN;
    rawAdvParams_.itvl_min = 0x30;
    rawAdvParams_.itvl_max = 0x50;
    rawAdvParams_.channel_map = 0x07;

    if (
        ble_gap_adv_set_data(
            wakeAdv_,
            sizeof(wakeAdv_)
        ) != 0
    )
    {
        setState("Wake advertisement failed");
        return false;
    }

    wakeBurst_ = 0;
    return startWakeBurst();
#else
    setState("NimBLE required");
    return false;
#endif
}

bool Switch2WakeBoot::startWakeBurst()
{
    if (wakeBurst_ >= WAKE_BURSTS)
    {
        if (liveWakeActive_)
        {
            finishLiveWake("Switch 2 wake beacon sent");
        }
        else
        {
            finishAndRestart("Switch 2 wake beacon sent");
        }
        return true;
    }

#if defined(CONFIG_NIMBLE_ENABLED)
    if (
        ble_gap_adv_start(
            BLE_OWN_ADDR_PUBLIC,
            nullptr,
            BLE_HS_FOREVER,
            &rawAdvParams_,
            nullptr,
            nullptr
        ) != 0
    )
    {
        setState("Wake advertising failed");
        return false;
    }

    phase_ = Phase::Advertising;
    phaseStartedAtMs_ = millis();
    setState("Broadcasting Switch 2 wake beacon");
    return true;
#else
    return false;
#endif
}

void Switch2WakeBoot::stopWakeBurst()
{
#if defined(CONFIG_NIMBLE_ENABLED)
    ble_gap_adv_stop();
#endif

    ++wakeBurst_;

    if (wakeBurst_ >= WAKE_BURSTS)
    {
        if (liveWakeActive_)
        {
            finishLiveWake("Switch 2 wake beacon sent");
        }
        else
        {
            finishAndRestart("Switch 2 wake beacon sent");
        }
    }
    else
    {
        phase_ = Phase::Gap;
        phaseStartedAtMs_ = millis();
    }
}

void Switch2WakeBoot::finishAndRestart(const char* state)
{
    clearPendingAction();

    if (scan_ != nullptr && scan_->isScanning())
    {
        scan_->stop();
    }

    if (advertising_ != nullptr)
    {
        advertising_->stop();
    }

    setState(state);
    phase_ = Phase::RestartPending;
    restartAtMs_ = millis() + RESTART_DELAY_MS;
}

void Switch2WakeBoot::finishLiveWake(const char* state)
{
#if defined(CONFIG_NIMBLE_ENABLED)
    if (ble_gap_adv_active())
    {
        ble_gap_adv_stop();
    }
#endif

    setState(state);
    liveWakeActive_ = false;
    phase_ = Phase::Idle;
}

void Switch2WakeBoot::clearPendingAction()
{
    prefs_.putUChar(
        "action",
        static_cast<std::uint8_t>(Action::None)
    );
}

bool Switch2WakeBoot::applyCapturedBtMac()
{
    return
        esp_iface_mac_addr_set(savedMac_, ESP_MAC_BT) == ESP_OK;
}

void Switch2WakeBoot::buildWakeAdvertisement()
{
    static constexpr std::uint8_t prefix[7] = {
        0x02, 0x01, 0x06,
        0x1B, 0xFF,
        0x53, 0x05
    };

    std::memcpy(wakeAdv_, prefix, sizeof(prefix));
    std::memcpy(
        wakeAdv_ + sizeof(prefix),
        savedPayload_,
        sizeof(savedPayload_)
    );

    // Reverse-engineered wake trigger: byte 16 of the complete advertisement.
    wakeAdv_[16] = WAKE_FLAG;
}

bool Switch2WakeBoot::parseMac(
    const String& text,
    std::uint8_t mac[6]
)
{
    unsigned int values[6] = {};

    if (
        std::sscanf(
            text.c_str(),
            "%02x:%02x:%02x:%02x:%02x:%02x",
            &values[0], &values[1], &values[2],
            &values[3], &values[4], &values[5]
        ) != 6
    )
    {
        return false;
    }

    for (std::size_t i = 0; i < 6; ++i)
    {
        mac[i] = static_cast<std::uint8_t>(values[i]);
    }

    return true;
}

void Switch2WakeBoot::updateMacText()
{
    std::snprintf(
        identityMacText_,
        sizeof(identityMacText_),
        "%02X:%02X:%02X:%02X:%02X:%02X",
        savedMac_[0], savedMac_[1], savedMac_[2],
        savedMac_[3], savedMac_[4], savedMac_[5]
    );
}


void Switch2WakeBoot::setState(const char* state)
{
    std::strncpy(state_, state, sizeof(state_) - 1);
    state_[sizeof(state_) - 1] = '\0';
}
