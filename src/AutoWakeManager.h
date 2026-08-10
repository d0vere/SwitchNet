#pragma once

#include <cstdint>

#include "Config.h"
#include "IControllerBackend.h"
#include "Switch2WakeBoot.h"
#include "UdpServer.h"

class AutoWakeManager
{
public:
    AutoWakeManager(
        UdpServer& udp,
        IControllerBackend& backend,
        Switch2WakeBoot& wake,
        Config& config
    );

    void update();
    void setEnabled(bool enabled);

    bool enabled() const;
    bool pending() const;
    bool hostActive() const;
    const char* switchUsbState() const;
    const char* lastReason() const;

    std::uint32_t attempts() const;
    std::uint32_t successes() const;
    std::uint32_t lastAttemptAgeMs() const;

private:
    static constexpr std::uint32_t UNMOUNTED_GRACE_MS = 800;
    static constexpr std::uint32_t MOUNTED_IDLE_GRACE_MS = 2200;
    static constexpr std::uint32_t GLOBAL_WAKE_COOLDOWN_MS = 10000;

    UdpServer& udp_;
    IControllerBackend& backend_;
    Switch2WakeBoot& wake_;
    Config& config_;

    bool previousClientConnected_ = false;
    bool pending_ = false;
    bool attemptedThisSession_ = false;

    std::uint32_t clientConnectedAtMs_ = 0;
    std::uint32_t lastAttemptAtMs_ = 0;
    std::uint32_t attempts_ = 0;
    std::uint32_t successes_ = 0;

    char lastReason_[64] = "idle";

    void beginClientSession();
    void endClientSession();
    void setReason(const char* reason);
};
