#pragma once

#include <WiFiUdp.h>

#include <cstdint>

#include "Config.h"
#include "ControllerState.h"
#include "IControllerBackend.h"
#include "PacketDecoder.h"
#include "RumbleState.h"
#include "SwitchNetProtocol.h"
#include "WifiManager.h"

class UdpServer
{
public:
    UdpServer(WifiManager& wifi, IControllerBackend& backend, Config& config);

    void begin(std::uint16_t port);
    void update();

    bool listening() const;
    bool clientConnected() const;
    String clientIp() const;
    std::uint16_t clientPort() const;

    std::uint8_t connectedControllerCount() const;
    bool slotConnected(std::uint8_t slot) const;
    String slotClientIp(std::uint8_t slot) const;
    std::uint16_t slotClientPort(std::uint8_t slot) const;
    std::uint32_t slotSessionId(std::uint8_t slot) const;
    std::uint32_t slotLastPacketAgeMs(std::uint8_t slot) const;

    std::uint32_t packetsPerSecond() const;
    std::uint32_t packetsReceived() const;
    std::uint32_t packetsLost() const;
    std::uint32_t invalidPackets() const;
    std::uint32_t crcErrors() const;
    std::uint32_t protocolErrors() const;
    std::uint32_t foreignPackets() const;
    std::uint32_t outOfOrderPackets() const;
    std::uint32_t lastSequence() const;
    std::uint32_t sessionId() const;
    std::uint32_t lastPacketAgeMs() const;
    std::uint32_t lastClientTimestampUs() const;
    std::uint32_t rumblePacketsSent() const;
    std::uint32_t rumbleSendFailures() const;
    std::uint32_t lastRumbleSequence() const;

    // Apply rumble forwarding immediately, without restarting the device.
    void applyRumbleEnabled(bool enabled);
    void applyRumbleIntensity(std::uint8_t percent);

    const ControllerState& controllerState() const;

private:
    static constexpr std::uint32_t CLIENT_TIMEOUT_MS = 1500;
    static constexpr int MAX_PACKETS_PER_UPDATE = 16;
    static constexpr std::size_t RECEIVE_BUFFER_SIZE = 96;

    WifiManager& wifi_;
    IControllerBackend& backend_;
    Config& config_;
    WiFiUDP udp_;
    PacketDecoder decoder_;

    std::uint16_t port_ = 5454;
    bool listening_ = false;

    struct ClientSlot
    {
        IPAddress ip{};
        std::uint16_t port = 0;
        std::uint32_t lastPacketAt = 0;
        bool connected = false;

        bool hasSequence = false;
        std::uint32_t sessionId = 0;
        std::uint32_t lastSequence = 0;
        std::uint32_t lastClientTimestampUs = 0;

        std::uint32_t lastForwardedRumbleSequence = 0;
        std::uint32_t rumblePacketSequence = 0;

        ControllerState state{};
    };

    ClientSlot clients_[
        SwitchNetProtocol::MAX_CONTROLLER_SLOTS
    ]{};

    std::uint32_t packetsReceived_ = 0;
    std::uint32_t packetsLost_ = 0;
    std::uint32_t invalidPackets_ = 0;
    std::uint32_t crcErrors_ = 0;
    std::uint32_t protocolErrors_ = 0;
    std::uint32_t foreignPackets_ = 0;
    std::uint32_t outOfOrderPackets_ = 0;

    std::uint32_t ppsWindowStartedAt_ = 0;
    std::uint32_t ppsWindowPackets_ = 0;
    std::uint32_t packetsPerSecond_ = 0;

    std::uint32_t rumblePacketsSent_ = 0;
    std::uint32_t rumbleSendFailures_ = 0;

    std::uint8_t receiveBuffer_[RECEIVE_BUFFER_SIZE]{};

    void startListening();
    void stopListening();
    void processPacket(int packetSize);
    void acceptClient(
        std::uint8_t slot,
        const IPAddress& ip,
        std::uint16_t port,
        std::uint32_t sessionId
    );
    void disconnectClient(std::uint8_t slot);
    void disconnectAllClients();
    void updatePacketsPerSecond();
    void forwardRumbleIfNeeded();
    void sendRumbleStopPacket(std::uint8_t slot);
    void registerDecodeError(PacketDecoder::Result result);
    static std::uint32_t crc32(const std::uint8_t* data, std::size_t size);
};
