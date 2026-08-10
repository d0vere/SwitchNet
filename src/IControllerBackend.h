#pragma once

#include <Arduino.h>

#include <cstdint>

#include "ControllerState.h"
#include "RumbleState.h"

class IControllerBackend
{
public:
    virtual ~IControllerBackend() = default;

    virtual void begin() = 0;
    virtual void update() = 0;
    virtual void setState(const ControllerState& state) = 0;
    virtual void reset() = 0;
    virtual void setSourceConnected(bool connected) { (void)connected; }

    virtual void setStateForSlot(
        std::uint8_t slot,
        const ControllerState& state
    )
    {
        if (slot == 0)
        {
            setState(state);
        }
    }

    virtual void resetSlot(std::uint8_t slot)
    {
        if (slot == 0)
        {
            reset();
        }
    }

    virtual void setSourceConnectedForSlot(
        std::uint8_t slot,
        bool connected
    )
    {
        if (slot == 0)
        {
            setSourceConnected(connected);
        }
    }

    virtual bool sourceConnectedForSlot(
        std::uint8_t slot
    ) const
    {
        return slot == 0
            ? sourceConnected()
            : false;
    }

    virtual const char* name() const = 0;
    virtual bool connected() const = 0;
    virtual bool started() const { return connected(); }
    virtual bool sourceConnected() const { return false; }

    virtual std::uint32_t reportsSent() const = 0;
    virtual std::uint32_t reportsPerSecond() const = 0;
    virtual std::uint32_t sendFailures() const = 0;

    virtual std::uint32_t outputReportsReceived() const { return 0; }
    virtual std::uint32_t handshakeResponsesSent() const { return 0; }
    virtual std::uint8_t lastOutputReportId() const { return 0; }
    virtual std::uint8_t lastCommand() const { return 0; }
    virtual bool usbOnlyMode() const { return false; }
    virtual bool reportMode30() const { return false; }

    // Experimental dual-HID lab diagnostics. Backends that do not implement
    // the Nintendo USB experiment remain valid and report neutral values.
    virtual bool dualHidLabEnabled() const { return false; }
    virtual bool dualHidSecondOpen() const { return false; }
    virtual std::uint32_t dualHidReportsSent() const { return 0; }
    virtual std::uint32_t dualHidOutputsReceived() const { return 0; }
    virtual String primaryIdentityMac() const { return String(); }
    virtual String secondaryIdentityMac() const { return String(); }
    virtual bool secondaryReportMode30() const { return false; }

    // Recent successful USB traffic is a stronger "console awake" signal than
    // VBUS/enumeration alone.
    virtual bool hostActive() const { return connected(); }
    virtual std::uint32_t lastHostActivityAgeMs() const
    {
        return 0xFFFFFFFFU;
    }

    virtual std::uint32_t outputReport80Count() const { return 0; }
    virtual std::uint32_t outputReport01Count() const { return 0; }
    virtual std::uint32_t outputReport10Count() const { return 0; }
    virtual std::uint32_t unknownOutputReportCount() const { return 0; }
    virtual std::uint32_t repliesQueued() const { return 0; }
    virtual std::uint32_t repliesDropped() const { return 0; }
    virtual std::uint16_t lastOutputLength() const { return 0; }
    virtual const char* lastOutputHex() const { return ""; }
    virtual const char* lastReplyHex() const { return ""; }

    virtual bool copyRumbleState(RumbleState& state) const
    {
        state = RumbleState{};
        return false;
    }

    virtual bool copyRumbleStateForSlot(
        std::uint8_t slot,
        RumbleState& state
    ) const
    {
        if (slot == 0)
        {
            return copyRumbleState(state);
        }

        state = RumbleState{};
        return false;
    }
};
