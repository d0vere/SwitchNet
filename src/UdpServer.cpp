#include "UdpServer.h"

#include "Crc32.h"

#include <Arduino.h>

#include <cstddef>
#include <cstring>

UdpServer::UdpServer(
    WifiManager& wifi,
    IControllerBackend& backend,
    Config& config
)
    : wifi_(wifi),
      backend_(backend),
      config_(config)
{
}

void UdpServer::begin(std::uint16_t port)
{
    port_ = port;
    ppsWindowStartedAt_ = millis();

    if (wifi_.connected())
    {
        startListening();
    }
}

void UdpServer::update()
{
    if (wifi_.connected() && !listening_)
    {
        startListening();
    }
    else if (!wifi_.connected() && listening_)
    {
        stopListening();
    }

    if (!listening_)
    {
        updatePacketsPerSecond();
        return;
    }

    for (
        int processed = 0;
        processed < MAX_PACKETS_PER_UPDATE;
        ++processed
    )
    {
        const int packetSize =
            udp_.parsePacket();

        if (packetSize <= 0)
        {
            break;
        }

        processPacket(packetSize);
    }

    forwardRumbleIfNeeded();

    const std::uint32_t now = millis();

    for (
        std::uint8_t slot = 0;
        slot < SwitchNetProtocol::MAX_CONTROLLER_SLOTS;
        ++slot
    )
    {
        if (
            clients_[slot].connected &&
            now - clients_[slot].lastPacketAt >=
                CLIENT_TIMEOUT_MS
        )
        {
            Serial.print("[UDP] Controller P");
            Serial.print(slot + 1);
            Serial.println(" timed out");
            disconnectClient(slot);
        }
    }

    updatePacketsPerSecond();
}

bool UdpServer::listening() const
{
    return listening_;
}

bool UdpServer::clientConnected() const
{
    return connectedControllerCount() > 0;
}

std::uint8_t UdpServer::connectedControllerCount() const
{
    std::uint8_t count = 0;

    for (
        const auto& client : clients_
    )
    {
        if (client.connected)
        {
            ++count;
        }
    }

    return count;
}

bool UdpServer::slotConnected(
    std::uint8_t slot
) const
{
    return
        slot <
            SwitchNetProtocol::MAX_CONTROLLER_SLOTS &&
        clients_[slot].connected;
}

String UdpServer::slotClientIp(
    std::uint8_t slot
) const
{
    return slotConnected(slot)
        ? clients_[slot].ip.toString()
        : String();
}

std::uint16_t UdpServer::slotClientPort(
    std::uint8_t slot
) const
{
    return slotConnected(slot)
        ? clients_[slot].port
        : 0;
}

std::uint32_t UdpServer::slotSessionId(
    std::uint8_t slot
) const
{
    return slotConnected(slot)
        ? clients_[slot].sessionId
        : 0;
}

std::uint32_t UdpServer::slotLastPacketAgeMs(
    std::uint8_t slot
) const
{
    return slotConnected(slot)
        ? millis() -
            clients_[slot].lastPacketAt
        : 0;
}

String UdpServer::clientIp() const
{
    if (clients_[0].connected)
    {
        return clients_[0].ip.toString();
    }

    return clients_[1].connected
        ? clients_[1].ip.toString()
        : String();
}

std::uint16_t UdpServer::clientPort() const
{
    if (clients_[0].connected)
    {
        return clients_[0].port;
    }

    return clients_[1].connected
        ? clients_[1].port
        : 0;
}

std::uint32_t UdpServer::packetsPerSecond() const
{
    return packetsPerSecond_;
}

std::uint32_t UdpServer::packetsReceived() const
{
    return packetsReceived_;
}

std::uint32_t UdpServer::packetsLost() const
{
    return packetsLost_;
}

std::uint32_t UdpServer::invalidPackets() const
{
    return invalidPackets_;
}

std::uint32_t UdpServer::crcErrors() const
{
    return crcErrors_;
}

std::uint32_t UdpServer::protocolErrors() const
{
    return protocolErrors_;
}

std::uint32_t UdpServer::foreignPackets() const
{
    return foreignPackets_;
}

std::uint32_t UdpServer::outOfOrderPackets() const
{
    return outOfOrderPackets_;
}

std::uint32_t UdpServer::lastSequence() const
{
    return clients_[0].lastSequence;
}

std::uint32_t UdpServer::sessionId() const
{
    return clients_[0].sessionId;
}

std::uint32_t UdpServer::lastClientTimestampUs() const
{
    return clients_[0].lastClientTimestampUs;
}

std::uint32_t UdpServer::rumblePacketsSent() const
{
    return rumblePacketsSent_;
}

std::uint32_t UdpServer::rumbleSendFailures() const
{
    return rumbleSendFailures_;
}

std::uint32_t UdpServer::lastRumbleSequence() const
{
    return
        clients_[0].lastForwardedRumbleSequence;
}

std::uint32_t UdpServer::lastPacketAgeMs() const
{
    if (clients_[0].connected)
    {
        return
            millis() -
            clients_[0].lastPacketAt;
    }

    if (clients_[1].connected)
    {
        return
            millis() -
            clients_[1].lastPacketAt;
    }

    return 0;
}

const ControllerState& UdpServer::controllerState() const
{
    return clients_[0].state;
}

void UdpServer::startListening()
{
    if (!udp_.begin(port_))
    {
        Serial.print(
            "[UDP] Failed to listen on port "
        );
        Serial.println(port_);
        return;
    }

    listening_ = true;

    Serial.print("[UDP] Listening on port ");
    Serial.println(port_);
}

void UdpServer::stopListening()
{
    udp_.stop();
    listening_ = false;
    disconnectAllClients();

    Serial.println("[UDP] Server stopped");
}

void UdpServer::processPacket(int packetSize)
{
    const IPAddress remoteIp =
        udp_.remoteIP();

    const std::uint16_t remotePort =
        udp_.remotePort();

    if (
        packetSize <= 0 ||
        packetSize >
            static_cast<int>(
                sizeof(receiveBuffer_)
            )
    )
    {
        while (udp_.available() > 0)
        {
            udp_.read();
        }

        ++invalidPackets_;
        ++protocolErrors_;
        return;
    }

    const int bytesRead =
        udp_.read(
            receiveBuffer_,
            sizeof(receiveBuffer_)
        );

    if (bytesRead != packetSize)
    {
        ++invalidPackets_;
        ++protocolErrors_;
        return;
    }

    ControllerState decodedState{};
    std::uint32_t decodedSessionId = 0;
    std::uint32_t decodedSequence = 0;
    std::uint32_t decodedTimestampUs = 0;
    std::uint8_t controllerSlot = 0;

    const PacketDecoder::Result result =
        decoder_.decode(
            receiveBuffer_,
            static_cast<std::size_t>(
                bytesRead
            ),
            decodedState,
            decodedSessionId,
            decodedSequence,
            decodedTimestampUs,
            controllerSlot
        );

    if (result != PacketDecoder::Result::Ok)
    {
        registerDecodeError(result);
        return;
    }

    if (
        controllerSlot >=
            SwitchNetProtocol::MAX_CONTROLLER_SLOTS
    )
    {
        ++invalidPackets_;
        ++protocolErrors_;
        return;
    }

    ClientSlot& client =
        clients_[controllerSlot];

    if (
        client.connected &&
        (
            remoteIp != client.ip ||
            remotePort != client.port
        )
    )
    {
        ++foreignPackets_;
        return;
    }

    if (!client.connected)
    {
        acceptClient(
            controllerSlot,
            remoteIp,
            remotePort,
            decodedSessionId
        );
    }
    else if (
        decodedSessionId != client.sessionId
    )
    {
        Serial.print("[UDP] P");
        Serial.print(controllerSlot + 1);
        Serial.println(
            " session changed; resetting sequence"
        );

        client.sessionId =
            decodedSessionId;
        client.hasSequence = false;
    }

    if (client.hasSequence)
    {
        const std::uint32_t delta =
            decodedSequence -
            client.lastSequence;

        if (
            delta == 0 ||
            delta >= 0x80000000U
        )
        {
            ++outOfOrderPackets_;
            return;
        }

        if (delta > 1)
        {
            packetsLost_ += delta - 1;
        }
    }

    client.lastSequence =
        decodedSequence;

    client.lastClientTimestampUs =
        decodedTimestampUs;

    client.hasSequence = true;
    client.lastPacketAt = millis();
    client.state = decodedState;

    backend_.setStateForSlot(
        controllerSlot,
        client.state
    );

    ++packetsReceived_;
    ++ppsWindowPackets_;
}

void UdpServer::acceptClient(
    std::uint8_t slot,
    const IPAddress& ip,
    std::uint16_t port,
    std::uint32_t sessionId
)
{
    if (
        slot >=
            SwitchNetProtocol::MAX_CONTROLLER_SLOTS
    )
    {
        return;
    }

    ClientSlot& client = clients_[slot];

    client.ip = ip;
    client.port = port;
    client.sessionId = sessionId;
    client.connected = true;
    client.hasSequence = false;
    client.lastForwardedRumbleSequence = 0;
    client.lastPacketAt = millis();

    wifi_.setLowLatencyMode(true);

    backend_.setSourceConnectedForSlot(
        slot,
        true
    );

    Serial.print("[UDP] P");
    Serial.print(slot + 1);
    Serial.print(" connected: ");
    Serial.print(client.ip);
    Serial.print(':');
    Serial.print(client.port);
    Serial.print(" session=");
    Serial.println(
        sessionId,
        HEX
    );
}

void UdpServer::disconnectClient(
    std::uint8_t slot
)
{
    if (
        slot >=
            SwitchNetProtocol::MAX_CONTROLLER_SLOTS
    )
    {
        return;
    }

    ClientSlot& client =
        clients_[slot];

    client = ClientSlot{};

    backend_.setSourceConnectedForSlot(
        slot,
        false
    );
    backend_.resetSlot(slot);

    if (!clientConnected())
    {
        wifi_.setLowLatencyMode(false);
        packetsPerSecond_ = 0;
        ppsWindowPackets_ = 0;
    }
}

void UdpServer::disconnectAllClients()
{
    for (
        std::uint8_t slot = 0;
        slot <
            SwitchNetProtocol::MAX_CONTROLLER_SLOTS;
        ++slot
    )
    {
        disconnectClient(slot);
    }
}

void UdpServer::updatePacketsPerSecond()
{
    const std::uint32_t now = millis();
    const std::uint32_t elapsed =
        now - ppsWindowStartedAt_;

    if (elapsed < 1000)
    {
        return;
    }

    packetsPerSecond_ =
        static_cast<std::uint32_t>(
            (
                static_cast<std::uint64_t>(
                    ppsWindowPackets_
                ) *
                1000ULL
            ) /
            elapsed
        );

    ppsWindowPackets_ = 0;
    ppsWindowStartedAt_ = now;
}

void UdpServer::applyRumbleEnabled(
    bool enabled
)
{
    if (config_.rumbleEnabled == enabled)
    {
        return;
    }

    const bool wasEnabled =
        config_.rumbleEnabled;

    config_.rumbleEnabled = enabled;

    if (wasEnabled && !enabled)
    {
        for (
            std::uint8_t slot = 0;
            slot <
                SwitchNetProtocol::MAX_CONTROLLER_SLOTS;
            ++slot
        )
        {
            sendRumbleStopPacket(slot);
        }
    }
    else if (!wasEnabled && enabled)
    {
        for (auto& client : clients_)
        {
            client.lastForwardedRumbleSequence = 0;
        }
    }
}

void UdpServer::applyRumbleIntensity(
    std::uint8_t percent
)
{
    if (percent > 100)
    {
        percent = 100;
    }

    if (config_.rumbleIntensity == percent)
    {
        return;
    }

    const std::uint8_t previous =
        config_.rumbleIntensity;

    config_.rumbleIntensity = percent;

    if (previous > 0 && percent == 0)
    {
        for (
            std::uint8_t slot = 0;
            slot <
                SwitchNetProtocol::MAX_CONTROLLER_SLOTS;
            ++slot
        )
        {
            sendRumbleStopPacket(slot);
        }

        return;
    }

    if (
        config_.rumbleEnabled &&
        percent > 0
    )
    {
        for (auto& client : clients_)
        {
            client.lastForwardedRumbleSequence = 0;
        }
    }
}

void UdpServer::sendRumbleStopPacket(
    std::uint8_t slot
)
{
    if (
        !listening_ ||
        !slotConnected(slot)
    )
    {
        return;
    }

    ClientSlot& client =
        clients_[slot];

    SwitchNetProtocol::RumblePacket packet{};
    packet.header.magic =
        SwitchNetProtocol::MAGIC;
    packet.header.version =
        SwitchNetProtocol::VERSION;
    packet.header.type =
        SwitchNetProtocol::PacketType::Rumble;
    packet.header.headerSize =
        static_cast<std::uint16_t>(
            SwitchNetProtocol::HEADER_SIZE
        );
    packet.header.payloadSize =
        static_cast<std::uint16_t>(
            SwitchNetProtocol::
                RUMBLE_PAYLOAD_SIZE
        );
    packet.header.flags =
        SwitchNetProtocol::
            flagsForControllerSlot(slot);
    packet.header.sessionId =
        client.sessionId;
    packet.header.sequence =
        client.rumblePacketSequence++;
    packet.header.clientTimestampUs =
        micros();

    std::memset(
        packet.rumble.raw,
        0,
        sizeof(packet.rumble.raw)
    );

    packet.rumble.holdMs = 0;
    packet.rumble.reserved =
        config_.rumbleIntensity;

    packet.crc32 =
        crc32(
            reinterpret_cast<
                const std::uint8_t*
            >(&packet),
            offsetof(
                SwitchNetProtocol::
                    RumblePacket,
                crc32
            )
        );

    if (
        udp_.beginPacket(
            client.ip,
            client.port
        ) &&
        udp_.write(
            reinterpret_cast<
                const std::uint8_t*
            >(&packet),
            sizeof(packet)
        ) == sizeof(packet) &&
        udp_.endPacket()
    )
    {
        ++rumblePacketsSent_;
    }
    else
    {
        ++rumbleSendFailures_;
    }
}

void UdpServer::forwardRumbleIfNeeded()
{
    if (
        !listening_ ||
        !config_.rumbleEnabled
    )
    {
        return;
    }

    for (
        std::uint8_t slot = 0;
        slot <
            SwitchNetProtocol::MAX_CONTROLLER_SLOTS;
        ++slot
    )
    {
        ClientSlot& client =
            clients_[slot];

        if (!client.connected)
        {
            continue;
        }

        RumbleState rumble{};

        if (
            !backend_.copyRumbleStateForSlot(
                slot,
                rumble
            ) ||
            rumble.sequence ==
                client.lastForwardedRumbleSequence
        )
        {
            continue;
        }

        SwitchNetProtocol::RumblePacket packet{};
        packet.header.magic =
            SwitchNetProtocol::MAGIC;
        packet.header.version =
            SwitchNetProtocol::VERSION;
        packet.header.type =
            SwitchNetProtocol::PacketType::Rumble;
        packet.header.headerSize =
            static_cast<std::uint16_t>(
                SwitchNetProtocol::HEADER_SIZE
            );
        packet.header.payloadSize =
            static_cast<std::uint16_t>(
                SwitchNetProtocol::
                    RUMBLE_PAYLOAD_SIZE
            );
        packet.header.flags =
            SwitchNetProtocol::
                flagsForControllerSlot(slot);
        packet.header.sessionId =
            client.sessionId;
        packet.header.sequence =
            client.rumblePacketSequence++;
        packet.header.clientTimestampUs =
            micros();

        std::memcpy(
            packet.rumble.raw,
            rumble.raw,
            sizeof(packet.rumble.raw)
        );

        packet.rumble.holdMs = 80;
        packet.rumble.reserved =
            config_.rumbleIntensity;

        packet.crc32 =
            crc32(
                reinterpret_cast<
                    const std::uint8_t*
                >(&packet),
                offsetof(
                    SwitchNetProtocol::
                        RumblePacket,
                    crc32
                )
            );

        if (
            udp_.beginPacket(
                client.ip,
                client.port
            ) &&
            udp_.write(
                reinterpret_cast<
                    const std::uint8_t*
                >(&packet),
                sizeof(packet)
            ) == sizeof(packet) &&
            udp_.endPacket()
        )
        {
            ++rumblePacketsSent_;
            client.lastForwardedRumbleSequence =
                rumble.sequence;
        }
        else
        {
            ++rumbleSendFailures_;
        }
    }
}

std::uint32_t UdpServer::crc32(
    const std::uint8_t* data,
    std::size_t size
)
{
    return SwitchNetCrc32::compute(
        data,
        size
    );
}

void UdpServer::registerDecodeError(
    PacketDecoder::Result result
)
{
    ++invalidPackets_;

    if (
        result ==
        PacketDecoder::Result::InvalidCrc
    )
    {
        ++crcErrors_;
    }
    else
    {
        ++protocolErrors_;
    }
}
