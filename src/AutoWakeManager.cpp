#include "AutoWakeManager.h"

#include <Arduino.h>
#include <cstring>

AutoWakeManager::AutoWakeManager(
    UdpServer& udp,
    IControllerBackend& backend,
    Switch2WakeBoot& wake,
    Config& config
)
    : udp_(udp),
      backend_(backend),
      wake_(wake),
      config_(config)
{
}

void AutoWakeManager::update()
{
    const bool clientConnected = udp_.clientConnected();

    if (clientConnected && !previousClientConnected_)
    {
        beginClientSession();
    }
    else if (!clientConnected && previousClientConnected_)
    {
        endClientSession();
    }

    previousClientConnected_ = clientConnected;

    if (!clientConnected || !pending_ || attemptedThisSession_)
    {
        return;
    }

    if (!config_.autoWakeEnabled)
    {
        pending_ = false;
        setReason("disabled");
        return;
    }

    if (!wake_.identityReady())
    {
        pending_ = false;
        setReason("wake_identity_not_ready");
        return;
    }

    if (backend_.hostActive())
    {
        pending_ = false;
        setReason("usb_host_active");
        return;
    }

    const std::uint32_t now = millis();
    const std::uint32_t elapsed = now - clientConnectedAtMs_;

    const std::uint32_t grace =
        backend_.connected()
            ? MOUNTED_IDLE_GRACE_MS
            : UNMOUNTED_GRACE_MS;

    if (elapsed < grace)
    {
        return;
    }

    if (
        lastAttemptAtMs_ != 0 &&
        now - lastAttemptAtMs_ < GLOBAL_WAKE_COOLDOWN_MS
    )
    {
        pending_ = false;
        setReason("wake_cooldown");
        return;
    }

    attemptedThisSession_ = true;
    pending_ = false;
    lastAttemptAtMs_ = now;
    ++attempts_;

    if (wake_.requestLiveWake())
    {
        ++successes_;
        setReason(
            backend_.connected()
                ? "client_connected_usb_idle"
                : "client_connected_usb_unavailable"
        );
    }
    else
    {
        setReason("wake_request_rejected");
    }
}

void AutoWakeManager::setEnabled(bool enabled)
{
    config_.autoWakeEnabled = enabled;

    if (!enabled)
    {
        pending_ = false;
        setReason("disabled");
        return;
    }

    if (udp_.clientConnected())
    {
        beginClientSession();
        previousClientConnected_ = true;
    }
}

bool AutoWakeManager::enabled() const
{
    return config_.autoWakeEnabled;
}

bool AutoWakeManager::pending() const
{
    return pending_;
}

bool AutoWakeManager::hostActive() const
{
    return backend_.hostActive();
}

const char* AutoWakeManager::switchUsbState() const
{
    if (backend_.hostActive())
    {
        return "awake";
    }

    if (!backend_.started())
    {
        return "unknown";
    }

    if (backend_.connected())
    {
        return "usb_idle_or_suspended";
    }

    return "sleep_or_unavailable";
}

const char* AutoWakeManager::lastReason() const
{
    return lastReason_;
}

std::uint32_t AutoWakeManager::attempts() const
{
    return attempts_;
}

std::uint32_t AutoWakeManager::successes() const
{
    return successes_;
}

std::uint32_t AutoWakeManager::lastAttemptAgeMs() const
{
    if (lastAttemptAtMs_ == 0)
    {
        return 0;
    }

    return millis() - lastAttemptAtMs_;
}

void AutoWakeManager::beginClientSession()
{
    clientConnectedAtMs_ = millis();
    attemptedThisSession_ = false;

    if (!config_.autoWakeEnabled)
    {
        pending_ = false;
        setReason("disabled");
        return;
    }

    if (!wake_.identityReady())
    {
        pending_ = false;
        setReason("wake_identity_not_ready");
        return;
    }

    pending_ = true;
    setReason("waiting_for_usb_state");
}

void AutoWakeManager::endClientSession()
{
    pending_ = false;
    attemptedThisSession_ = false;
    setReason("idle");
}

void AutoWakeManager::setReason(const char* reason)
{
    if (reason == nullptr)
    {
        lastReason_[0] = '\0';
        return;
    }

    std::strncpy(lastReason_, reason, sizeof(lastReason_) - 1);
    lastReason_[sizeof(lastReason_) - 1] = '\0';
}
