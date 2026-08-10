#pragma once

#include <USB.h>
#include <USBHID.h>

#include <cstddef>
#include <cstdint>

#include "IControllerBackend.h"

class NintendoProControllerBackend final : public IControllerBackend, public USBHIDDevice
{
public:
    NintendoProControllerBackend();

    void begin() override;
    void update() override;
    void setState(const ControllerState& state) override;
    void reset() override;
    void setSourceConnected(bool connected) override;

    void setStateForSlot(
        std::uint8_t slot,
        const ControllerState& state
    ) override;
    void resetSlot(std::uint8_t slot) override;
    void setSourceConnectedForSlot(
        std::uint8_t slot,
        bool connected
    ) override;
    bool sourceConnectedForSlot(
        std::uint8_t slot
    ) const override;

    const char* name() const override;
    bool connected() const override;
    bool started() const override;
    bool sourceConnected() const override;

    std::uint32_t reportsSent() const override;
    std::uint32_t reportsPerSecond() const override;
    std::uint32_t sendFailures() const override;

    std::uint32_t outputReportsReceived() const override;
    std::uint32_t handshakeResponsesSent() const override;
    std::uint8_t lastOutputReportId() const override;
    std::uint8_t lastCommand() const override;
    bool usbOnlyMode() const override;
    bool reportMode30() const override;
    bool hostActive() const override;
    std::uint32_t lastHostActivityAgeMs() const override;

    std::uint32_t outputReport80Count() const override;
    std::uint32_t outputReport01Count() const override;
    std::uint32_t outputReport10Count() const override;
    std::uint32_t unknownOutputReportCount() const override;
    std::uint32_t repliesQueued() const override;
    std::uint32_t repliesDropped() const override;
    std::uint16_t lastOutputLength() const override;
    const char* lastOutputHex() const override;
    const char* lastReplyHex() const override;
    bool copyRumbleState(RumbleState& state) const override;
    bool copyRumbleStateForSlot(
        std::uint8_t slot,
        RumbleState& state
    ) const override;

    void setDualHidLabEnabled(bool enabled);
    bool dualHidLabEnabled() const override;
    bool dualHidSecondOpen() const override;
    std::uint32_t dualHidReportsSent() const override;
    std::uint32_t dualHidOutputsReceived() const override;
    String primaryIdentityMac() const override;
    String secondaryIdentityMac() const override;
    bool secondaryReportMode30() const override;

    static const std::uint8_t* reportDescriptor();
    static std::uint16_t reportDescriptorLength();

    void processSecondaryOutput(
        std::uint8_t reportId,
        const std::uint8_t* buffer,
        std::uint16_t len
    );

    uint16_t _onGetDescriptor(uint8_t* buffer) override;
    void _onOutput(uint8_t reportId, const uint8_t* buffer, uint16_t len) override;
    void _onSetFeature(uint8_t reportId, const uint8_t* buffer, uint16_t len) override;

private:
    static constexpr std::uint32_t REPORT_INTERVAL_US = 4000;
    static constexpr std::size_t REPORT_PAYLOAD_SIZE = 63;
    static constexpr std::size_t REPLY_QUEUE_SIZE = 8;
    static constexpr std::size_t DIAGNOSTIC_BYTES = 20;
    static constexpr std::size_t DIAGNOSTIC_TEXT_SIZE = DIAGNOSTIC_BYTES * 3 + 1;

    struct Reply
    {
        std::uint8_t reportId = 0;
        std::uint8_t data[REPORT_PAYLOAD_SIZE]{};
    };

    USBHID hid_;
    ControllerState state_{};
    ControllerState secondaryState_{};

    bool prepared_ = false;
    bool sourceConnected_ = false;
    bool secondarySourceConnected_ = false;
    bool started_ = false;
    bool usbOnlyMode_ = false;
    bool reportMode30_ = false;
    bool dualHidLabEnabled_ = false;
    std::uint8_t timer_ = 0;
    std::uint8_t secondaryTimer_ = 0;
    std::uint8_t mac_[6]{};
    std::uint8_t secondaryMac_[6]{};
    bool secondaryUsbOnlyMode_ = false;
    bool secondaryReportMode30_ = false;
    std::uint8_t stickCalibration_[18]{};
    std::uint8_t userCalibration_[0x100]{};
    std::uint32_t nextReportAtUs_ = 0;

    std::uint32_t reportsSent_ = 0;
    std::uint32_t sendFailures_ = 0;
    std::uint32_t rateWindowStartedAtMs_ = 0;
    std::uint32_t rateWindowReports_ = 0;
    std::uint32_t reportsPerSecond_ = 0;
    volatile std::uint32_t lastHostActivityAtMs_ = 0;

    volatile std::uint32_t outputReportsReceived_ = 0;
    volatile std::uint32_t handshakeResponsesSent_ = 0;
    volatile std::uint8_t lastOutputReportId_ = 0;
    volatile std::uint8_t lastCommand_ = 0;
    volatile std::uint16_t lastOutputLength_ = 0;
    volatile std::uint32_t outputReport80Count_ = 0;
    volatile std::uint32_t outputReport01Count_ = 0;
    volatile std::uint32_t outputReport10Count_ = 0;
    volatile std::uint32_t unknownOutputReportCount_ = 0;
    volatile std::uint32_t repliesQueued_ = 0;
    volatile std::uint32_t repliesDropped_ = 0;

    char lastOutputHex_[DIAGNOSTIC_TEXT_SIZE]{};
    char lastReplyHex_[DIAGNOSTIC_TEXT_SIZE]{};

    Reply replyQueue_[REPLY_QUEUE_SIZE]{};
    volatile std::uint8_t replyHead_ = 0;
    volatile std::uint8_t replyTail_ = 0;

    Reply secondaryReplyQueue_[REPLY_QUEUE_SIZE]{};
    volatile std::uint8_t secondaryReplyHead_ = 0;
    volatile std::uint8_t secondaryReplyTail_ = 0;

    portMUX_TYPE queueMux_ = portMUX_INITIALIZER_UNLOCKED;
    portMUX_TYPE diagnosticMux_ = portMUX_INITIALIZER_UNLOCKED;
    mutable portMUX_TYPE rumbleMux_ = portMUX_INITIALIZER_UNLOCKED;
    RumbleState rumbleState_{};
    RumbleState secondaryRumbleState_{};

    void startUsb();
    void initializeIdentity();
    void buildStickCalibration();
    void handleOutputReport(std::uint8_t reportId, const std::uint8_t* payload, std::uint16_t length);
    void handleUsbHandshake(const std::uint8_t* payload, std::uint16_t length);
    void handleSubcommand(const std::uint8_t* payload, std::uint16_t length);

    void handleSecondaryOutputReport(std::uint8_t reportId, const std::uint8_t* payload, std::uint16_t length);
    void handleSecondaryUsbHandshake(const std::uint8_t* payload, std::uint16_t length);
    void handleSecondarySubcommand(const std::uint8_t* payload, std::uint16_t length);

    void captureRumble(const std::uint8_t* raw, std::uint16_t length);
    void captureSecondaryRumble(
        const std::uint8_t* raw,
        std::uint16_t length
    );

    bool enqueueReply(std::uint8_t reportId, const std::uint8_t* data, std::size_t length);
    bool dequeueReply(Reply& reply);
    bool sendQueuedReply();

    bool enqueueSecondaryReply(std::uint8_t reportId, const std::uint8_t* data, std::size_t length);
    bool dequeueSecondaryReply(Reply& reply);
    bool sendSecondaryQueuedReply();

    void buildInputPrefix(std::uint8_t* report);
    void buildInputPrefixWithTimer(
        std::uint8_t* report,
        std::uint8_t& timer,
        const ControllerState& state
    );
    void buildSubcommandReply(
        std::uint8_t subcommand,
        const std::uint8_t* arguments,
        std::uint16_t argumentLength,
        std::uint8_t* reply
    );
    void buildSubcommandReplyForIdentity(
        std::uint8_t subcommand,
        const std::uint8_t* arguments,
        std::uint16_t argumentLength,
        std::uint8_t* reply,
        const std::uint8_t identityMac[6],
        bool& reportMode,
        std::uint8_t& timer,
        const ControllerState& controllerState
    );
    void readSpi(std::uint32_t address, std::uint8_t length, std::uint8_t* destination) const;
    void writeSpi(
        std::uint32_t address,
        std::uint8_t length,
        const std::uint8_t* source,
        std::uint16_t available
    );

    void sendInputReport();
    void updateReportRate();
    void captureOutput(std::uint8_t reportId, const std::uint8_t* payload, std::uint16_t length);
    void captureReply(std::uint8_t reportId, const std::uint8_t* payload, std::size_t length);
    static void formatHex(char* destination, std::size_t destinationSize, std::uint8_t reportId, const std::uint8_t* payload, std::size_t length);

    static void packStick(std::uint8_t* destination, std::int16_t x, std::int16_t y);
    static std::uint16_t mapAxis12(std::int16_t value);
    static void packCalibration12(std::uint8_t* destination, const std::uint16_t values[6]);
};
