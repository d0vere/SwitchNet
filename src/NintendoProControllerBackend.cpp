#include "NintendoProControllerBackend.h"
#include "DualHidBridge.h"

#include <Arduino.h>

#include <algorithm>
#include <cstring>

#ifndef ARDUINO_USB_MODE
#error "SwitchNet requires native USB support"
#elif ARDUINO_USB_MODE == 1
#error "SwitchNet Nintendo backend requires USB Mode = USB-OTG (TinyUSB)"
#endif

namespace
{
constexpr std::uint8_t REPORT_DESCRIPTOR[] = {
    0x05,0x01,0x15,0x00,0x09,0x04,0xA1,0x01,0x85,0x30,0x05,0x01,
    0x05,0x09,0x19,0x01,0x29,0x0A,0x15,0x00,0x25,0x01,0x75,0x01,
    0x95,0x0A,0x55,0x00,0x65,0x00,0x81,0x02,0x05,0x09,0x19,0x0B,
    0x29,0x0E,0x15,0x00,0x25,0x01,0x75,0x01,0x95,0x04,0x81,0x02,
    0x75,0x01,0x95,0x02,0x81,0x03,0x0B,0x01,0x00,0x01,0x00,0xA1,
    0x00,0x0B,0x30,0x00,0x01,0x00,0x0B,0x31,0x00,0x01,0x00,0x0B,
    0x32,0x00,0x01,0x00,0x0B,0x35,0x00,0x01,0x00,0x15,0x00,0x27,
    0xFF,0xFF,0x00,0x00,0x75,0x10,0x95,0x04,0x81,0x02,0xC0,0x0B,
    0x39,0x00,0x01,0x00,0x15,0x00,0x25,0x07,0x35,0x00,0x46,0x3B,
    0x01,0x65,0x14,0x75,0x04,0x95,0x01,0x81,0x42,0x05,0x09,0x19,
    0x0F,0x29,0x12,0x15,0x00,0x25,0x01,0x75,0x01,0x95,0x04,0x81,
    0x02,0x75,0x08,0x95,0x34,0x81,0x03,0x06,0x00,0xFF,0x85,0x21,
    0x09,0x01,0x75,0x08,0x95,0x3F,0x81,0x03,0x85,0x81,0x09,0x02,
    0x75,0x08,0x95,0x3F,0x81,0x03,0x85,0x01,0x09,0x03,0x75,0x08,
    0x95,0x3F,0x91,0x83,0x85,0x10,0x09,0x04,0x75,0x08,0x95,0x3F,
    0x91,0x83,0x85,0x80,0x09,0x05,0x75,0x08,0x95,0x3F,0x91,0x83,
    0x85,0x82,0x09,0x06,0x75,0x08,0x95,0x3F,0x91,0x83,0xC0
};

static_assert(sizeof(REPORT_DESCRIPTOR) == 203, "Unexpected Nintendo HID descriptor size");

constexpr std::uint8_t SPI_IMU_CAL[24] = {
    0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x40,0x00,0x40,0x00,0x40,
    0x00,0x00,0x00,0x00,0x00,0x00,
    0x3B,0x34,0x3B,0x34,0x3B,0x34
};

constexpr std::uint8_t SPI_PARAMS1[24] = {
    0x50,0xFD,0x00,0x00,0xC6,0x0F,
    0x0F,0x30,0x61,0x96,0x30,0xF3,
    0xD4,0x14,0x54,0x41,0x15,0x54,
    0xC7,0x79,0x9C,0x33,0x36,0x63
};

constexpr std::uint8_t SPI_PARAMS2[18] = {
    0x0F,0x30,0x61,0x96,0x30,0xF3,
    0xD4,0x14,0x54,0x41,0x15,0x54,
    0xC7,0x79,0x9C,0x33,0x36,0x63
};

constexpr std::uint8_t SPI_COLOR[13] = {
    0x32,0x32,0x32,0xE6,0xE6,0xE6,0x32,
    0x32,0x32,0x32,0x32,0x32,0xFF
};

constexpr std::uint8_t BT_PAIR_2[31] = {
    0x02,0xE5,0xC8,0xE4,0x92,0x05,0xFF,0xC9,0x8A,0x7D,0xEA,
    0x15,0xF6,0x19,0xBA,0x82,0x13,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00
};

constexpr std::uint8_t BT_PAIR_3[31] = {0x03};
constexpr std::uint8_t CONTROLLER_NAME[14] = {
    0x50,0x72,0x6F,0x20,0x43,0x6F,0x6E,
    0x74,0x72,0x6F,0x6C,0x6C,0x65,0x72
};
}

NintendoProControllerBackend::NintendoProControllerBackend()
{
    USBHID::addDevice(this, sizeof(REPORT_DESCRIPTOR));
}

void NintendoProControllerBackend::begin()
{
    DualHidBridge::configure(
        this,
        dualHidLabEnabled_
    );

    initializeIdentity();
    buildStickCalibration();
    std::memset(userCalibration_, 0xFF, sizeof(userCalibration_));
    prepared_ = true;
    rateWindowStartedAtMs_ = millis();
}

void NintendoProControllerBackend::startUsb()
{
    if (!prepared_ || started_)
    {
        return;
    }

    USB.VID(0x057E);
    USB.PID(0x2009);
    USB.manufacturerName("Nintendo Co., Ltd.");
    USB.productName("Pro Controller");
    USB.serialNumber("000000000001");
    USB.firmwareVersion(0x0220);
    USB.usbVersion(0x0200);
    USB.usbClass(0x00);
    USB.usbSubClass(0x00);
    USB.usbProtocol(0x00);
    USB.usbAttributes(0xA0);
    USB.usbPower(500);

    // The HID descriptor must be registered before TinyUSB starts. Once mounted,
    // the USB personality remains active even if the UDP source times out.
    hid_.begin();
    started_ = USB.begin();
    reportMode30_ = false;
    usbOnlyMode_ = false;
    replyHead_ = 0;
    replyTail_ = 0;
    nextReportAtUs_ = micros();
    rateWindowStartedAtMs_ = millis();
}

void NintendoProControllerBackend::update()
{
    updateReportRate();

    if (
        (sourceConnected_ || secondarySourceConnected_) &&
        !started_
    )
    {
        startUsb();
    }

    if (!started_ || !connected())
    {
        return;
    }

    if (sendQueuedReply())
    {
        return;
    }

    if (
        dualHidLabEnabled_ &&
        sendSecondaryQueuedReply()
    )
    {
        return;
    }

    if (
        !reportMode30_ &&
        !(dualHidLabEnabled_ && secondaryReportMode30_)
    )
    {
        return;
    }

    const std::uint32_t now = micros();
    if (static_cast<std::int32_t>(now - nextReportAtUs_) < 0)
    {
        return;
    }

    nextReportAtUs_ += REPORT_INTERVAL_US;
    if (static_cast<std::int32_t>(now - nextReportAtUs_) >= 0)
    {
        nextReportAtUs_ = now + REPORT_INTERVAL_US;
    }

    sendInputReport();
}

void NintendoProControllerBackend::setState(
    const ControllerState& state
)
{
    setStateForSlot(0, state);
}

void NintendoProControllerBackend::setStateForSlot(
    std::uint8_t slot,
    const ControllerState& state
)
{
    if (slot == 0)
    {
        state_ = state;
    }
    else if (slot == 1)
    {
        secondaryState_ = state;
    }
}

void NintendoProControllerBackend::reset()
{
    state_ = ControllerState{};
    secondaryState_ = ControllerState{};
}

void NintendoProControllerBackend::resetSlot(
    std::uint8_t slot
)
{
    if (slot == 0)
    {
        state_ = ControllerState{};
    }
    else if (slot == 1)
    {
        secondaryState_ = ControllerState{};
    }
}

void NintendoProControllerBackend::setSourceConnected(
    bool connected
)
{
    setSourceConnectedForSlot(0, connected);
}

void NintendoProControllerBackend::setSourceConnectedForSlot(
    std::uint8_t slot,
    bool connected
)
{
    if (slot == 0)
    {
        sourceConnected_ = connected;

        if (!connected)
        {
            state_ = ControllerState{};
        }
    }
    else if (slot == 1)
    {
        secondarySourceConnected_ = connected;

        if (!connected)
        {
            secondaryState_ = ControllerState{};
        }
    }
}

bool NintendoProControllerBackend::sourceConnectedForSlot(
    std::uint8_t slot
) const
{
    if (slot == 0)
    {
        return sourceConnected_;
    }

    if (slot == 1)
    {
        return secondarySourceConnected_;
    }

    return false;
}


const char* NintendoProControllerBackend::name() const
{
    return "nintendo_pro_usb_openpuck_deferred";
}

bool NintendoProControllerBackend::connected() const
{
    return started_ && static_cast<bool>(USB);
}

bool NintendoProControllerBackend::started() const { return started_; }
bool NintendoProControllerBackend::sourceConnected() const
{
    return sourceConnected_ || secondarySourceConnected_;
}

std::uint32_t NintendoProControllerBackend::reportsSent() const { return reportsSent_; }
std::uint32_t NintendoProControllerBackend::reportsPerSecond() const { return reportsPerSecond_; }
std::uint32_t NintendoProControllerBackend::sendFailures() const { return sendFailures_; }
std::uint32_t NintendoProControllerBackend::outputReportsReceived() const { return outputReportsReceived_; }
std::uint32_t NintendoProControllerBackend::handshakeResponsesSent() const { return handshakeResponsesSent_; }
std::uint8_t NintendoProControllerBackend::lastOutputReportId() const { return lastOutputReportId_; }
std::uint8_t NintendoProControllerBackend::lastCommand() const { return lastCommand_; }
bool NintendoProControllerBackend::usbOnlyMode() const { return usbOnlyMode_; }
bool NintendoProControllerBackend::reportMode30() const { return reportMode30_; }

bool NintendoProControllerBackend::hostActive() const
{
    if (!started_ || !connected() || lastHostActivityAtMs_ == 0)
    {
        return false;
    }

    return millis() - lastHostActivityAtMs_ <= 1500U;
}

std::uint32_t NintendoProControllerBackend::lastHostActivityAgeMs() const
{
    if (lastHostActivityAtMs_ == 0)
    {
        return 0xFFFFFFFFU;
    }

    return millis() - lastHostActivityAtMs_;
}
std::uint32_t NintendoProControllerBackend::outputReport80Count() const { return outputReport80Count_; }
std::uint32_t NintendoProControllerBackend::outputReport01Count() const { return outputReport01Count_; }
std::uint32_t NintendoProControllerBackend::outputReport10Count() const { return outputReport10Count_; }
std::uint32_t NintendoProControllerBackend::unknownOutputReportCount() const { return unknownOutputReportCount_; }
std::uint32_t NintendoProControllerBackend::repliesQueued() const { return repliesQueued_; }
std::uint32_t NintendoProControllerBackend::repliesDropped() const { return repliesDropped_; }
std::uint16_t NintendoProControllerBackend::lastOutputLength() const { return lastOutputLength_; }
const char* NintendoProControllerBackend::lastOutputHex() const { return lastOutputHex_; }
const char* NintendoProControllerBackend::lastReplyHex() const { return lastReplyHex_; }

void NintendoProControllerBackend::setDualHidLabEnabled(bool enabled)
{
    dualHidLabEnabled_ = enabled;
    DualHidBridge::configure(this, enabled);
}

bool NintendoProControllerBackend::dualHidLabEnabled() const
{
    return dualHidLabEnabled_;
}

bool NintendoProControllerBackend::dualHidSecondOpen() const
{
    return DualHidBridge::secondOpen();
}

std::uint32_t NintendoProControllerBackend::dualHidReportsSent() const
{
    return DualHidBridge::reportsSent();
}

std::uint32_t NintendoProControllerBackend::dualHidOutputsReceived() const
{
    return DualHidBridge::outputsReceived();
}

String NintendoProControllerBackend::primaryIdentityMac() const
{
    char text[18] = {};

    snprintf(
        text,
        sizeof(text),
        "%02X:%02X:%02X:%02X:%02X:%02X",
        mac_[0],mac_[1],mac_[2],
        mac_[3],mac_[4],mac_[5]
    );

    return String(text);
}

String NintendoProControllerBackend::secondaryIdentityMac() const
{
    char text[18] = {};

    snprintf(
        text,
        sizeof(text),
        "%02X:%02X:%02X:%02X:%02X:%02X",
        secondaryMac_[0],secondaryMac_[1],secondaryMac_[2],
        secondaryMac_[3],secondaryMac_[4],secondaryMac_[5]
    );

    return String(text);
}

bool NintendoProControllerBackend::secondaryReportMode30() const
{
    return secondaryReportMode30_;
}

const std::uint8_t* NintendoProControllerBackend::reportDescriptor()
{
    return REPORT_DESCRIPTOR;
}

std::uint16_t NintendoProControllerBackend::reportDescriptorLength()
{
    return sizeof(REPORT_DESCRIPTOR);
}

void NintendoProControllerBackend::processSecondaryOutput(
    std::uint8_t reportId,
    const std::uint8_t* buffer,
    std::uint16_t len
)
{
    outputReportsReceived_ = outputReportsReceived_ + 1;
    lastHostActivityAtMs_ = millis();

    std::uint8_t effectiveReportId = reportId;
    const std::uint8_t* payload = buffer;
    std::uint16_t payloadLength = len;

    if (effectiveReportId == 0 && payloadLength > 0)
    {
        effectiveReportId = payload[0];
        payload += 1;
        payloadLength -= 1;
    }

    lastOutputReportId_ = effectiveReportId;
    lastCommand_ = payloadLength > 0 ? payload[0] : 0;
    lastOutputLength_ = payloadLength;
    captureOutput(
        effectiveReportId,
        payload,
        payloadLength
    );

    handleSecondaryOutputReport(
        effectiveReportId,
        payload,
        payloadLength
    );
}

bool NintendoProControllerBackend::copyRumbleState(RumbleState& state) const
{
    bool available = false;
    portENTER_CRITICAL(&rumbleMux_);
    state = rumbleState_;
    available = state.sequence != 0;
    portEXIT_CRITICAL(&rumbleMux_);
    return available;
}

bool NintendoProControllerBackend::copyRumbleStateForSlot(
    std::uint8_t slot,
    RumbleState& state
) const
{
    if (slot == 0)
    {
        return copyRumbleState(state);
    }

    if (slot != 1)
    {
        state = RumbleState{};
        return false;
    }

    bool available = false;
    portENTER_CRITICAL(&rumbleMux_);
    state = secondaryRumbleState_;
    available = state.sequence != 0;
    portEXIT_CRITICAL(&rumbleMux_);
    return available;
}

uint16_t NintendoProControllerBackend::_onGetDescriptor(uint8_t* buffer)
{
    std::memcpy(
        buffer,
        reportDescriptor(),
        reportDescriptorLength()
    );
    return reportDescriptorLength();
}

void NintendoProControllerBackend::_onOutput(
    uint8_t reportId,
    const uint8_t* buffer,
    uint16_t len
)
{
    outputReportsReceived_ = outputReportsReceived_ + 1;
    lastHostActivityAtMs_ = millis();

    std::uint8_t effectiveReportId = reportId;
    const std::uint8_t* payload = buffer;
    std::uint16_t payloadLength = len;

    // TinyUSB may deliver endpoint-OUT reports with the report ID in byte zero.
    if (effectiveReportId == 0 && payloadLength > 0)
    {
        effectiveReportId = payload[0];
        payload += 1;
        payloadLength -= 1;
    }

    lastOutputReportId_ = effectiveReportId;
    lastCommand_ = payloadLength > 0 ? payload[0] : 0;
    lastOutputLength_ = payloadLength;
    captureOutput(effectiveReportId, payload, payloadLength);

    handleOutputReport(effectiveReportId, payload, payloadLength);
}

void NintendoProControllerBackend::_onSetFeature(
    uint8_t reportId,
    const uint8_t* buffer,
    uint16_t len
)
{
    // ESP32 Arduino Core 3.3.x routes every SET_REPORT request with a
    // non-zero report ID through _onSetFeature(), even when the HID report
    // type is OUTPUT. The Linux hid-nintendo driver uses that control path
    // during initialization, so process it exactly like an OUT report.
    _onOutput(reportId, buffer, len);
}

void NintendoProControllerBackend::initializeIdentity()
{
    const std::uint64_t efuse = ESP.getEfuseMac();

    // OpenPuck uses a stable per-controller MAC. Keep the same byte order used
    // by the Nintendo protocol and derive a locally unique value from eFuse.
    mac_[0] = 0x7C;
    mac_[1] = 0xBB;
    mac_[2] = 0x8A;
    mac_[3] = static_cast<std::uint8_t>(efuse >> 16U);
    mac_[4] = static_cast<std::uint8_t>(efuse >> 8U);
    mac_[5] = static_cast<std::uint8_t>(efuse);

    std::memcpy(
        secondaryMac_,
        mac_,
        sizeof(secondaryMac_)
    );

    // Keep the same locally administered identity family but force HID2 to a
    // different stable Nintendo controller identity. Avoid wrapping back onto
    // P1 when the final byte is 0xFF.
    secondaryMac_[5] =
        mac_[5] == 0xFF
            ? static_cast<std::uint8_t>(0xFE)
            : static_cast<std::uint8_t>(mac_[5] + 1U);
}

void NintendoProControllerBackend::buildStickCalibration()
{
    constexpr std::uint16_t center = 2048;
    constexpr std::uint16_t range = 1800;

    const std::uint16_t left[6] = {range, range, center, center, range, range};
    const std::uint16_t right[6] = {center, center, range, range, range, range};

    packCalibration12(stickCalibration_, left);
    packCalibration12(stickCalibration_ + 9, right);
}

void NintendoProControllerBackend::handleOutputReport(
    std::uint8_t reportId,
    const std::uint8_t* payload,
    std::uint16_t length
)
{
    if (reportId == 0x80)
    {
        outputReport80Count_ = outputReport80Count_ + 1;
        handleUsbHandshake(payload, length);
        return;
    }

    if (reportId == 0x01)
    {
        outputReport01Count_ = outputReport01Count_ + 1;
        // [timer][4-byte left rumble][4-byte right rumble][subcommand]...
        if (length >= 9)
        {
            captureRumble(payload + 1, 8);
        }
        handleSubcommand(payload, length);
        return;
    }

    if (reportId == 0x10)
    {
        outputReport10Count_ = outputReport10Count_ + 1;
        // Stand-alone rumble report has the same timer + 8-byte payload prefix.
        if (length >= 9)
        {
            captureRumble(payload + 1, 8);
        }
        return;
    }

    unknownOutputReportCount_ = unknownOutputReportCount_ + 1;
    // Report 0x82 and other unsupported output reports are intentionally ignored.
}

void NintendoProControllerBackend::handleSecondaryOutputReport(
    std::uint8_t reportId,
    const std::uint8_t* payload,
    std::uint16_t length
)
{
    if (reportId == 0x80)
    {
        outputReport80Count_ =
            outputReport80Count_ + 1;

        handleSecondaryUsbHandshake(
            payload,
            length
        );
        return;
    }

    if (reportId == 0x01)
    {
        outputReport01Count_ =
            outputReport01Count_ + 1;

        if (length >= 9)
        {
            // Keep rumble forwarding shared for this lab; identity/protocol
            // state is separate, but the physical source controller is one.
            captureSecondaryRumble(
                payload + 1,
                8
            );
        }

        handleSecondarySubcommand(
            payload,
            length
        );
        return;
    }

    if (reportId == 0x10)
    {
        outputReport10Count_ =
            outputReport10Count_ + 1;

        if (length >= 9)
        {
            captureSecondaryRumble(
                payload + 1,
                8
            );
        }

        return;
    }

    unknownOutputReportCount_ =
        unknownOutputReportCount_ + 1;
}

void NintendoProControllerBackend::handleSecondaryUsbHandshake(
    const std::uint8_t* payload,
    std::uint16_t length
)
{
    if (length < 1)
    {
        return;
    }

    const std::uint8_t command = payload[0];
    lastCommand_ = command;

    if (command == 0x01)
    {
        const std::uint8_t reply[9] = {
            0x01,0x00,0x03,
            secondaryMac_[0],
            secondaryMac_[1],
            secondaryMac_[2],
            secondaryMac_[3],
            secondaryMac_[4],
            secondaryMac_[5]
        };

        enqueueSecondaryReply(
            0x81,
            reply,
            sizeof(reply)
        );
    }
    else if (
        command == 0x02 ||
        command == 0x03
    )
    {
        const std::uint8_t reply[1] = {
            command
        };

        enqueueSecondaryReply(
            0x81,
            reply,
            sizeof(reply)
        );
    }
    else if (command == 0x04)
    {
        secondaryUsbOnlyMode_ = true;
    }
    else if (
        command == 0x05 ||
        command == 0x06
    )
    {
        secondaryUsbOnlyMode_ = false;

        if (command == 0x06)
        {
            secondaryReportMode30_ = false;
        }
    }
}

void NintendoProControllerBackend::handleSecondarySubcommand(
    const std::uint8_t* payload,
    std::uint16_t length
)
{
    if (length < 10)
    {
        return;
    }

    const std::uint8_t subcommand =
        payload[9];

    lastCommand_ = subcommand;

    std::uint8_t reply[REPORT_PAYLOAD_SIZE]{};

    buildSubcommandReplyForIdentity(
        subcommand,
        payload + 10,
        static_cast<std::uint16_t>(
            length - 10
        ),
        reply,
        secondaryMac_,
        secondaryReportMode30_,
        secondaryTimer_,
        secondaryState_
    );

    enqueueSecondaryReply(
        0x21,
        reply,
        sizeof(reply)
    );
}

void NintendoProControllerBackend::handleUsbHandshake(
    const std::uint8_t* payload,
    std::uint16_t length
)
{
    if (length < 1)
    {
        return;
    }

    const std::uint8_t command = payload[0];
    lastCommand_ = command;

    if (command == 0x01)
    {
        std::uint8_t reply[9] = {
            0x01,0x00,0x03,
            mac_[0],mac_[1],mac_[2],mac_[3],mac_[4],mac_[5]
        };
        enqueueReply(0x81, reply, sizeof(reply));
    }
    else if (command == 0x02 || command == 0x03)
    {
        const std::uint8_t reply[1] = {command};
        enqueueReply(0x81, reply, sizeof(reply));
    }
    else if (command == 0x04)
    {
        // OpenPuck and a genuine controller do not reply to force-USB.
        usbOnlyMode_ = true;
    }
    else if (command == 0x05 || command == 0x06)
    {
        // No reply expected for timeout-enable/reset either.
        usbOnlyMode_ = false;
        if (command == 0x06)
        {
            reportMode30_ = false;
        }
    }
}

void NintendoProControllerBackend::handleSubcommand(
    const std::uint8_t* payload,
    std::uint16_t length
)
{
    // [timer][8 rumble bytes][subcommand][arguments...]
    if (length < 10)
    {
        return;
    }

    const std::uint8_t subcommand = payload[9];
    lastCommand_ = subcommand;

    std::uint8_t reply[REPORT_PAYLOAD_SIZE]{};
    buildSubcommandReply(
        subcommand,
        payload + 10,
        static_cast<std::uint16_t>(length - 10),
        reply
    );
    enqueueReply(0x21, reply, sizeof(reply));
}

void NintendoProControllerBackend::captureRumble(const std::uint8_t* raw, std::uint16_t length)
{
    if (raw == nullptr || length < 8)
    {
        return;
    }

    portENTER_CRITICAL(&rumbleMux_);
    std::memcpy(rumbleState_.raw, raw, 8);
    rumbleState_.sequence += 1;
    if (rumbleState_.sequence == 0)
    {
        rumbleState_.sequence = 1;
    }
    rumbleState_.updatedAtMs = millis();
    portEXIT_CRITICAL(&rumbleMux_);
}

void NintendoProControllerBackend::captureSecondaryRumble(
    const std::uint8_t* raw,
    std::uint16_t length
)
{
    if (raw == nullptr || length < 8)
    {
        return;
    }

    portENTER_CRITICAL(&rumbleMux_);
    std::memcpy(
        secondaryRumbleState_.raw,
        raw,
        8
    );
    secondaryRumbleState_.sequence += 1;

    if (secondaryRumbleState_.sequence == 0)
    {
        secondaryRumbleState_.sequence = 1;
    }

    secondaryRumbleState_.updatedAtMs =
        millis();
    portEXIT_CRITICAL(&rumbleMux_);
}


bool NintendoProControllerBackend::enqueueReply(
    std::uint8_t reportId,
    const std::uint8_t* data,
    std::size_t length
)
{
    bool queued = false;

    portENTER_CRITICAL(&queueMux_);
    const std::uint8_t tail = replyTail_;
    const std::uint8_t next = static_cast<std::uint8_t>((tail + 1U) % REPLY_QUEUE_SIZE);

    if (next != replyHead_)
    {
        Reply& reply = replyQueue_[tail];
        reply.reportId = reportId;
        std::memset(reply.data, 0, sizeof(reply.data));
        std::memcpy(reply.data, data, std::min(length, sizeof(reply.data)));
        replyTail_ = next;
        queued = true;
    }
    portEXIT_CRITICAL(&queueMux_);

    if (queued)
    {
        repliesQueued_ = repliesQueued_ + 1;
        captureReply(reportId, data, length);
    }
    else
    {
        repliesDropped_ = repliesDropped_ + 1;
    }

    return queued;
}

bool NintendoProControllerBackend::dequeueReply(Reply& reply)
{
    bool available = false;

    portENTER_CRITICAL(&queueMux_);
    if (replyHead_ != replyTail_)
    {
        reply = replyQueue_[replyHead_];
        replyHead_ = static_cast<std::uint8_t>((replyHead_ + 1U) % REPLY_QUEUE_SIZE);
        available = true;
    }
    portEXIT_CRITICAL(&queueMux_);

    return available;
}

bool NintendoProControllerBackend::sendQueuedReply()
{
    Reply reply;

    if (!dequeueReply(reply))
    {
        return false;
    }

    if (
        hid_.SendReport(
            reply.reportId,
            reply.data,
            sizeof(reply.data),
            20
        )
    )
    {
        lastHostActivityAtMs_ = millis();
        handshakeResponsesSent_ =
            handshakeResponsesSent_ + 1;
        reportsSent_ += 1;
        rateWindowReports_ += 1;
    }
    else
    {
        sendFailures_ += 1;
        enqueueReply(
            reply.reportId,
            reply.data,
            sizeof(reply.data)
        );
    }

    return true;
}

bool NintendoProControllerBackend::enqueueSecondaryReply(
    std::uint8_t reportId,
    const std::uint8_t* data,
    std::size_t length
)
{
    bool queued = false;

    portENTER_CRITICAL(&queueMux_);

    const std::uint8_t tail =
        secondaryReplyTail_;

    const std::uint8_t next =
        static_cast<std::uint8_t>(
            (tail + 1U) % REPLY_QUEUE_SIZE
        );

    if (next != secondaryReplyHead_)
    {
        Reply& reply =
            secondaryReplyQueue_[tail];

        reply.reportId = reportId;

        std::memset(
            reply.data,
            0,
            sizeof(reply.data)
        );

        std::memcpy(
            reply.data,
            data,
            std::min(
                length,
                sizeof(reply.data)
            )
        );

        secondaryReplyTail_ = next;
        queued = true;
    }

    portEXIT_CRITICAL(&queueMux_);

    if (queued)
    {
        repliesQueued_ =
            repliesQueued_ + 1;
    }
    else
    {
        repliesDropped_ =
            repliesDropped_ + 1;
    }

    return queued;
}

bool NintendoProControllerBackend::dequeueSecondaryReply(
    Reply& reply
)
{
    bool available = false;

    portENTER_CRITICAL(&queueMux_);

    if (
        secondaryReplyHead_ !=
        secondaryReplyTail_
    )
    {
        reply =
            secondaryReplyQueue_[
                secondaryReplyHead_
            ];

        secondaryReplyHead_ =
            static_cast<std::uint8_t>(
                (
                    secondaryReplyHead_ +
                    1U
                ) %
                REPLY_QUEUE_SIZE
            );

        available = true;
    }

    portEXIT_CRITICAL(&queueMux_);

    return available;
}

bool NintendoProControllerBackend::sendSecondaryQueuedReply()
{
    if (!DualHidBridge::ready())
    {
        return false;
    }

    Reply reply;

    if (!dequeueSecondaryReply(reply))
    {
        return false;
    }

    if (
        DualHidBridge::send(
            reply.reportId,
            reply.data,
            sizeof(reply.data)
        )
    )
    {
        lastHostActivityAtMs_ = millis();
        handshakeResponsesSent_ =
            handshakeResponsesSent_ + 1;
    }
    else
    {
        sendFailures_ += 1;

        enqueueSecondaryReply(
            reply.reportId,
            reply.data,
            sizeof(reply.data)
        );
    }

    return true;
}


void NintendoProControllerBackend::buildInputPrefix(std::uint8_t* report)
{
    buildInputPrefixWithTimer(
        report,
        timer_,
        state_
    );
}

void NintendoProControllerBackend::buildInputPrefixWithTimer(
    std::uint8_t* report,
    std::uint8_t& timer,
    const ControllerState& controllerState
)
{
    report[0] = timer++;
    report[1] = 0x80; // full battery, wireless-style connection state as OpenPuck

    if (isPressed(controllerState, ControllerButton::Y)) report[2] |= 0x01;
    if (isPressed(controllerState, ControllerButton::X)) report[2] |= 0x02;
    if (isPressed(controllerState, ControllerButton::B)) report[2] |= 0x04;
    if (isPressed(controllerState, ControllerButton::A)) report[2] |= 0x08;
    if (isPressed(controllerState, ControllerButton::RightShoulder)) report[2] |= 0x40;
    if (controllerState.rightTrigger > 32767) report[2] |= 0x80;

    if (isPressed(controllerState, ControllerButton::Back)) report[3] |= 0x01;
    if (isPressed(controllerState, ControllerButton::Start)) report[3] |= 0x02;
    if (isPressed(controllerState, ControllerButton::RightStick)) report[3] |= 0x04;
    if (isPressed(controllerState, ControllerButton::LeftStick)) report[3] |= 0x08;
    if (isPressed(controllerState, ControllerButton::Guide)) report[3] |= 0x10;
    if (isPressed(controllerState, ControllerButton::Capture)) report[3] |= 0x20;

    if (isPressed(controllerState, ControllerButton::LeftShoulder)) report[4] |= 0x40;
    if (controllerState.leftTrigger > 32767) report[4] |= 0x80;

    switch (controllerState.hat)
    {
        case 0: report[4] |= 0x02; break;
        case 1: report[4] |= 0x02 | 0x04; break;
        case 2: report[4] |= 0x04; break;
        case 3: report[4] |= 0x04 | 0x01; break;
        case 4: report[4] |= 0x01; break;
        case 5: report[4] |= 0x01 | 0x08; break;
        case 6: report[4] |= 0x08; break;
        case 7: report[4] |= 0x08 | 0x02; break;
        default: break;
    }

    const auto invertAxis = [](std::int16_t value) -> std::int16_t
    {
        return value == INT16_MIN ? INT16_MAX : static_cast<std::int16_t>(-value);
    };

    packStick(report + 5, controllerState.leftX, invertAxis(controllerState.leftY));
    packStick(report + 8, controllerState.rightX, invertAxis(controllerState.rightY));
    report[11] = 0x09;
}

void NintendoProControllerBackend::buildSubcommandReply(
    std::uint8_t subcommand,
    const std::uint8_t* arguments,
    std::uint16_t argumentLength,
    std::uint8_t* reply
)
{
    buildSubcommandReplyForIdentity(
        subcommand,
        arguments,
        argumentLength,
        reply,
        mac_,
        reportMode30_,
        timer_,
        state_
    );
}

void NintendoProControllerBackend::buildSubcommandReplyForIdentity(
    std::uint8_t subcommand,
    const std::uint8_t* arguments,
    std::uint16_t argumentLength,
    std::uint8_t* reply,
    const std::uint8_t identityMac[6],
    bool& reportMode,
    std::uint8_t& timer,
    const ControllerState& controllerState
)
{
    std::memset(reply, 0, REPORT_PAYLOAD_SIZE);
    buildInputPrefixWithTimer(
        reply,
        timer,
        controllerState
    );
    reply[13] = subcommand;

    switch (subcommand)
    {
        case 0x01:
        {
            const std::uint8_t type = argumentLength >= 1 ? arguments[0] : 3;
            reply[12] = 0x81;

            if (type == 1)
            {
                reply[14] = 0x01;
                std::memcpy(reply + 15, identityMac, 6);
                reply[21] = 0x00;
                reply[22] = 0x25;
                reply[23] = 0x08;
                std::memcpy(reply + 24, CONTROLLER_NAME, sizeof(CONTROLLER_NAME));
                reply[43] = 0x68;
            }
            else if (type == 2)
            {
                std::memcpy(reply + 14, BT_PAIR_2, sizeof(BT_PAIR_2));
            }
            else
            {
                std::memcpy(reply + 14, BT_PAIR_3, sizeof(BT_PAIR_3));
            }
            break;
        }

        case 0x02:
            reply[12] = 0x82;
            reply[14] = 0x03;
            reply[15] = 0x48; // firmware 3.72
            reply[16] = 0x03; // Pro Controller
            reply[17] = 0x02;
            std::memcpy(reply + 18, identityMac, 6);
            reply[24] = 0x01;
            reply[25] = 0x01;
            break;

        case 0x03:
            if (argumentLength >= 1 && arguments[0] == 0x30)
            {
                reportMode = true;
                nextReportAtUs_ = micros() + REPORT_INTERVAL_US;
            }
            reply[12] = 0x80;
            break;

        case 0x04:
            reply[12] = 0x83;
            reply[14] = 0x00;
            reply[15] = 0xCC;
            reply[16] = 0x00;
            reply[17] = 0xEE;
            reply[18] = 0x00;
            reply[19] = 0xFF;
            break;

        case 0x10:
            if (argumentLength < 5)
            {
                reply[12] = 0x80;
                break;
            }
            else
            {
                const std::uint32_t address =
                    static_cast<std::uint32_t>(arguments[0]) |
                    (static_cast<std::uint32_t>(arguments[1]) << 8U) |
                    (static_cast<std::uint32_t>(arguments[2]) << 16U) |
                    (static_cast<std::uint32_t>(arguments[3]) << 24U);
                const std::uint8_t readLength = std::min<std::uint8_t>(arguments[4], 0x1D);

                reply[12] = 0x90;
                std::memcpy(reply + 14, arguments, 4);
                reply[18] = readLength;
                readSpi(address, readLength, reply + 19);
            }
            break;

        case 0x11:
            if (argumentLength >= 5)
            {
                const std::uint32_t address =
                    static_cast<std::uint32_t>(arguments[0]) |
                    (static_cast<std::uint32_t>(arguments[1]) << 8U) |
                    (static_cast<std::uint32_t>(arguments[2]) << 16U) |
                    (static_cast<std::uint32_t>(arguments[3]) << 24U);
                writeSpi(
                    address,
                    arguments[4],
                    arguments + 5,
                    argumentLength > 5 ? static_cast<std::uint16_t>(argumentLength - 5) : 0
                );
            }
            reply[12] = 0x80;
            break;

        case 0x21:
            reply[12] = 0xA0;
            break;

        default:
            reply[12] = 0x80;
            break;
    }
}

void NintendoProControllerBackend::readSpi(
    std::uint32_t address,
    std::uint8_t length,
    std::uint8_t* destination
) const
{
    for (std::uint8_t index = 0; index < length; ++index)
    {
        const std::uint32_t current = address + index;
        std::uint8_t value = 0xFF;

        if (current >= 0x6020 && current < 0x6020 + sizeof(SPI_IMU_CAL))
        {
            value = SPI_IMU_CAL[current - 0x6020];
        }
        else if (current >= 0x603D && current < 0x603D + sizeof(stickCalibration_))
        {
            value = stickCalibration_[current - 0x603D];
        }
        else if (current >= 0x6050 && current < 0x6050 + sizeof(SPI_COLOR))
        {
            value = SPI_COLOR[current - 0x6050];
        }
        else if (current >= 0x6080 && current < 0x6080 + sizeof(SPI_PARAMS1))
        {
            value = SPI_PARAMS1[current - 0x6080];
        }
        else if (current >= 0x6098 && current < 0x6098 + sizeof(SPI_PARAMS2))
        {
            value = SPI_PARAMS2[current - 0x6098];
        }
        else if (current >= 0x8000 && current < 0x8100)
        {
            value = userCalibration_[current - 0x8000];
        }

        destination[index] = value;
    }
}

void NintendoProControllerBackend::writeSpi(
    std::uint32_t address,
    std::uint8_t length,
    const std::uint8_t* source,
    std::uint16_t available
)
{
    const std::uint16_t count = std::min<std::uint16_t>(length, available);
    for (std::uint16_t index = 0; index < count; ++index)
    {
        const std::uint32_t current = address + index;
        if (current >= 0x8000 && current < 0x8100)
        {
            userCalibration_[current - 0x8000] = source[index];
        }
    }
}

void NintendoProControllerBackend::sendInputReport()
{
    const auto fillImu =
        [](std::uint8_t* report,
           const ControllerState& state)
    {
        const std::int16_t imu[6] = {
            state.accelX,
            state.accelY,
            state.accelZ,
            state.gyroX,
            state.gyroY,
            state.gyroZ
        };

        for (
            std::size_t sample = 0;
            sample < 3;
            ++sample
        )
        {
            const std::size_t offset =
                12 + sample * 12;

            for (
                std::size_t axis = 0;
                axis < 6;
                ++axis
            )
            {
                const std::uint16_t raw =
                    static_cast<std::uint16_t>(
                        imu[axis]
                    );

                report[offset + axis * 2] =
                    static_cast<std::uint8_t>(
                        raw & 0xFFU
                    );

                report[
                    offset + axis * 2 + 1
                ] =
                    static_cast<std::uint8_t>(
                        (raw >> 8U) & 0xFFU
                    );
            }
        }
    };

    bool primarySent = true;
    bool secondarySent = true;

    if (reportMode30_)
    {
        std::uint8_t report[
            REPORT_PAYLOAD_SIZE
        ]{};

        buildInputPrefixWithTimer(
            report,
            timer_,
            state_
        );
        fillImu(report, state_);

        primarySent =
            hid_.SendReport(
                0x30,
                report,
                sizeof(report),
                10
            );
    }

    if (
        dualHidLabEnabled_ &&
        secondaryReportMode30_
    )
    {
        std::uint8_t report[
            REPORT_PAYLOAD_SIZE
        ]{};

        buildInputPrefixWithTimer(
            report,
            secondaryTimer_,
            secondaryState_
        );
        fillImu(
            report,
            secondaryState_
        );

        secondarySent =
            DualHidBridge::send(
                0x30,
                report,
                sizeof(report)
            );
    }

    if (primarySent && secondarySent)
    {
        lastHostActivityAtMs_ = millis();
        reportsSent_ += 1;
        rateWindowReports_ += 1;
    }
    else
    {
        sendFailures_ += 1;
    }
}

void NintendoProControllerBackend::updateReportRate()
{
    const std::uint32_t now = millis();
    const std::uint32_t elapsed = now - rateWindowStartedAtMs_;
    if (elapsed < 1000)
    {
        return;
    }

    reportsPerSecond_ = static_cast<std::uint32_t>(
        (static_cast<std::uint64_t>(rateWindowReports_) * 1000ULL) / elapsed
    );

    rateWindowReports_ = 0;
    rateWindowStartedAtMs_ = now;
}


void NintendoProControllerBackend::captureOutput(
    std::uint8_t reportId,
    const std::uint8_t* payload,
    std::uint16_t length
)
{
    char formatted[DIAGNOSTIC_TEXT_SIZE]{};
    formatHex(formatted, sizeof(formatted), reportId, payload, length);

    portENTER_CRITICAL(&diagnosticMux_);
    std::memcpy(lastOutputHex_, formatted, sizeof(lastOutputHex_));
    portEXIT_CRITICAL(&diagnosticMux_);
}

void NintendoProControllerBackend::captureReply(
    std::uint8_t reportId,
    const std::uint8_t* payload,
    std::size_t length
)
{
    char formatted[DIAGNOSTIC_TEXT_SIZE]{};
    formatHex(formatted, sizeof(formatted), reportId, payload, length);

    portENTER_CRITICAL(&diagnosticMux_);
    std::memcpy(lastReplyHex_, formatted, sizeof(lastReplyHex_));
    portEXIT_CRITICAL(&diagnosticMux_);
}

void NintendoProControllerBackend::formatHex(
    char* destination,
    std::size_t destinationSize,
    std::uint8_t reportId,
    const std::uint8_t* payload,
    std::size_t length
)
{
    static constexpr char HEX_DIGITS[] = "0123456789ABCDEF";
    if (destinationSize == 0)
    {
        return;
    }

    std::size_t written = 0;
    const auto appendByte = [&](std::uint8_t value)
    {
        if (written + 3 >= destinationSize)
        {
            return false;
        }
        if (written != 0)
        {
            destination[written++] = ' ';
        }
        destination[written++] = HEX_DIGITS[value >> 4U];
        destination[written++] = HEX_DIGITS[value & 0x0FU];
        return true;
    };

    appendByte(reportId);
    const std::size_t count = std::min<std::size_t>(length, DIAGNOSTIC_BYTES - 1);
    for (std::size_t index = 0; index < count; ++index)
    {
        if (!appendByte(payload[index]))
        {
            break;
        }
    }
    destination[written] = '\0';
}

void NintendoProControllerBackend::packStick(
    std::uint8_t* destination,
    std::int16_t x,
    std::int16_t y
)
{
    const std::uint16_t packedX = mapAxis12(x);
    const std::uint16_t packedY = mapAxis12(y);

    destination[0] = static_cast<std::uint8_t>(packedX & 0xFFU);
    destination[1] = static_cast<std::uint8_t>(
        ((packedX >> 8U) & 0x0FU) | ((packedY & 0x0FU) << 4U)
    );
    destination[2] = static_cast<std::uint8_t>((packedY >> 4U) & 0xFFU);
}

std::uint16_t NintendoProControllerBackend::mapAxis12(std::int16_t value)
{
    const std::int32_t shifted = static_cast<std::int32_t>(value) + 32768;
    return static_cast<std::uint16_t>((shifted * 4095L) / 65535L);
}

void NintendoProControllerBackend::packCalibration12(
    std::uint8_t* destination,
    const std::uint16_t values[6]
)
{
    destination[0] = values[0] & 0xFF;
    destination[1] = ((values[1] & 0x0F) << 4) | ((values[0] >> 8) & 0x0F);
    destination[2] = (values[1] >> 4) & 0xFF;
    destination[3] = values[2] & 0xFF;
    destination[4] = ((values[3] & 0x0F) << 4) | ((values[2] >> 8) & 0x0F);
    destination[5] = (values[3] >> 4) & 0xFF;
    destination[6] = values[4] & 0xFF;
    destination[7] = ((values[5] & 0x0F) << 4) | ((values[4] >> 8) & 0x0F);
    destination[8] = (values[5] >> 4) & 0xFF;
}
