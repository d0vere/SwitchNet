#include "DiscoveryService.h"
#include "Version.h"

#include <cctype>
#include <cerrno>
#include <cstdio>
#include <cstring>

#include <lwip/inet.h>
#include <lwip/sockets.h>

DiscoveryService::DiscoveryService(
    WifiManager& wifi,
    const Config& config
)
    : wifi_(wifi),
      config_(config)
{
}

void DiscoveryService::begin()
{
    normalizeHostname(
        config_.hostname[0] != '\0'
            ? config_.hostname
            : "switchnet",
        hostname_,
        sizeof(hostname_)
    );

    wasConnected_ = wifi_.connected();

    if (wasConnected_)
    {
        startNetworkServices();
    }
}

void DiscoveryService::update()
{
    const bool connected = wifi_.connected();

    if (connected && !wasConnected_)
    {
        startNetworkServices();
    }
    else if (!connected && wasConnected_)
    {
        stopNetworkServices();
    }

    wasConnected_ = connected;

    if (connected)
    {
        maintainMdnsResponder();

        if (udpReady_)
        {
            handleUdpDiscovery();
        }
    }
}

bool DiscoveryService::mdnsReady() const
{
    return mdnsReady_;
}

bool DiscoveryService::udpReady() const
{
    return udpReady_;
}

std::uint32_t DiscoveryService::requests() const
{
    return requests_;
}

std::uint32_t DiscoveryService::mdnsQueries() const
{
    return mdnsQueries_;
}

std::uint32_t DiscoveryService::mdnsResponses() const
{
    return mdnsResponses_;
}

std::uint32_t DiscoveryService::mdnsRestarts() const
{
    return mdnsRestarts_;
}

std::uint32_t DiscoveryService::mdnsErrors() const
{
    return mdnsErrors_;
}

const char* DiscoveryService::hostname() const
{
    return hostname_;
}

void DiscoveryService::startNetworkServices()
{
    stopNetworkServices();

    lastIp_ = static_cast<std::uint32_t>(WiFi.localIP());

    mdnsReady_ = startMdnsResponder();
    udpReady_ = udp_.begin(DISCOVERY_PORT) == 1;
}

void DiscoveryService::stopNetworkServices()
{
    if (udpReady_)
    {
        udp_.stop();
    }

    udpReady_ = false;
    stopMdnsResponder(true);
    lastIp_ = 0;
}

bool DiscoveryService::startMdnsResponder()
{
    stopMdnsResponder(false);

    const IPAddress localIp = WiFi.localIP();

    if (
        WiFi.status() != WL_CONNECTED ||
        localIp == IPAddress(0, 0, 0, 0)
    )
    {
        mdnsReady_ = false;
        return false;
    }

    mdnsSocket_ = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);

    if (mdnsSocket_ < 0)
    {
        ++mdnsErrors_;
        mdnsReady_ = false;
        return false;
    }

    int reuse = 1;
    ::setsockopt(
        mdnsSocket_,
        SOL_SOCKET,
        SO_REUSEADDR,
        &reuse,
        sizeof(reuse)
    );

    sockaddr_in bindAddress{};
    bindAddress.sin_family = AF_INET;
    bindAddress.sin_port = htons(MDNS_PORT);
    bindAddress.sin_addr.s_addr = htonl(INADDR_ANY);

    if (
        ::bind(
            mdnsSocket_,
            reinterpret_cast<sockaddr*>(&bindAddress),
            sizeof(bindAddress)
        ) < 0
    )
    {
        ++mdnsErrors_;
        ::close(mdnsSocket_);
        mdnsSocket_ = -1;
        mdnsReady_ = false;
        return false;
    }

    ip_mreq membership{};
    membership.imr_multiaddr.s_addr =
        inet_addr("224.0.0.251");

    const String ipText = localIp.toString();
    membership.imr_interface.s_addr =
        inet_addr(ipText.c_str());

    if (
        ::setsockopt(
            mdnsSocket_,
            IPPROTO_IP,
            IP_ADD_MEMBERSHIP,
            &membership,
            sizeof(membership)
        ) < 0
    )
    {
        ++mdnsErrors_;
        ::close(mdnsSocket_);
        mdnsSocket_ = -1;
        mdnsReady_ = false;
        return false;
    }

    unsigned char ttl = 255;
    ::setsockopt(
        mdnsSocket_,
        IPPROTO_IP,
        IP_MULTICAST_TTL,
        &ttl,
        sizeof(ttl)
    );

    unsigned char loopback = 0;
    ::setsockopt(
        mdnsSocket_,
        IPPROTO_IP,
        IP_MULTICAST_LOOP,
        &loopback,
        sizeof(loopback)
    );

    mdnsReady_ = true;
    lastMdnsRetryAt_ = millis();
    lastAnnouncementAt_ = 0;

    announcementBurstRemaining_ = 2;
    nextBurstAnnouncementAt_ = millis() + 100;

    Serial.print("[MDNS] SwitchNet responder ready: http://");
    Serial.print(hostname_);
    Serial.println(".local");

    return true;
}

void DiscoveryService::stopMdnsResponder(bool goodbye)
{
    if (mdnsSocket_ >= 0)
    {
        if (goodbye && mdnsReady_)
        {
            sendMdnsAnnouncement(0);
        }

        ip_mreq membership{};
        membership.imr_multiaddr.s_addr =
            inet_addr("224.0.0.251");

        const String ipText = WiFi.localIP().toString();
        membership.imr_interface.s_addr =
            inet_addr(ipText.c_str());

        ::setsockopt(
            mdnsSocket_,
            IPPROTO_IP,
            IP_DROP_MEMBERSHIP,
            &membership,
            sizeof(membership)
        );

        ::close(mdnsSocket_);
    }

    mdnsSocket_ = -1;
    mdnsReady_ = false;
    announcementBurstRemaining_ = 0;
}

void DiscoveryService::maintainMdnsResponder()
{
    const std::uint32_t now = millis();
    const std::uint32_t currentIp =
        static_cast<std::uint32_t>(WiFi.localIP());

    if (currentIp != 0 && currentIp != lastIp_)
    {
        lastIp_ = currentIp;
        ++mdnsRestarts_;
        startMdnsResponder();
    }

    if (!mdnsReady_)
    {
        if (now - lastMdnsRetryAt_ >= MDNS_RETRY_MS)
        {
            lastMdnsRetryAt_ = now;
            ++mdnsRestarts_;
            startMdnsResponder();
        }

        return;
    }

    handleMdnsQueries();

    if (
        announcementBurstRemaining_ > 0 &&
        static_cast<std::int32_t>(
            now - nextBurstAnnouncementAt_
        ) >= 0
    )
    {
        sendMdnsAnnouncement();
        --announcementBurstRemaining_;

        if (announcementBurstRemaining_ > 0)
        {
            nextBurstAnnouncementAt_ = now + 1000;
        }
    }
    else if (
        announcementBurstRemaining_ == 0 &&
        (
            lastAnnouncementAt_ == 0 ||
            now - lastAnnouncementAt_ >=
                MDNS_ANNOUNCE_INTERVAL_MS
        )
    )
    {
        sendMdnsAnnouncement();
    }
}

static bool mdnsAppendU16(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    std::uint16_t value
)
{
    if (length + 2 > capacity) return false;
    buffer[length++] = static_cast<std::uint8_t>((value >> 8) & 0xFF);
    buffer[length++] = static_cast<std::uint8_t>(value & 0xFF);
    return true;
}

static bool mdnsAppendU32(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    std::uint32_t value
)
{
    if (length + 4 > capacity) return false;
    buffer[length++] = static_cast<std::uint8_t>((value >> 24) & 0xFF);
    buffer[length++] = static_cast<std::uint8_t>((value >> 16) & 0xFF);
    buffer[length++] = static_cast<std::uint8_t>((value >> 8) & 0xFF);
    buffer[length++] = static_cast<std::uint8_t>(value & 0xFF);
    return true;
}

static bool mdnsAppendName(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    const char* name
)
{
    if (name == nullptr) return false;

    const char* cursor = name;

    while (*cursor != '\0')
    {
        const char* dot = std::strchr(cursor, '.');
        const std::size_t labelLength =
            dot == nullptr
                ? std::strlen(cursor)
                : static_cast<std::size_t>(dot - cursor);

        if (
            labelLength == 0 ||
            labelLength > 63 ||
            length + 1 + labelLength > capacity
        )
        {
            return false;
        }

        buffer[length++] = static_cast<std::uint8_t>(labelLength);
        std::memcpy(buffer + length, cursor, labelLength);
        length += labelLength;

        if (dot == nullptr) break;
        cursor = dot + 1;
    }

    if (length + 1 > capacity) return false;
    buffer[length++] = 0;
    return true;
}

static bool mdnsAppendRecordHeader(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    const char* owner,
    std::uint16_t type,
    bool cacheFlush,
    std::uint32_t ttl,
    std::size_t& rdLengthOffset
)
{
    if (
        !mdnsAppendName(buffer, capacity, length, owner) ||
        !mdnsAppendU16(buffer, capacity, length, type) ||
        !mdnsAppendU16(
            buffer,
            capacity,
            length,
            static_cast<std::uint16_t>(
                1U | (cacheFlush ? 0x8000U : 0U)
            )
        ) ||
        !mdnsAppendU32(buffer, capacity, length, ttl)
    )
    {
        return false;
    }

    rdLengthOffset = length;
    return mdnsAppendU16(buffer, capacity, length, 0);
}

static void mdnsPatchRdLength(
    std::uint8_t* buffer,
    std::size_t rdLengthOffset,
    std::size_t rdataStart,
    std::size_t length
)
{
    const std::uint16_t rdLength =
        static_cast<std::uint16_t>(length - rdataStart);

    buffer[rdLengthOffset] =
        static_cast<std::uint8_t>((rdLength >> 8) & 0xFF);
    buffer[rdLengthOffset + 1] =
        static_cast<std::uint8_t>(rdLength & 0xFF);
}

static bool mdnsAppendARecord(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    const char* hostName,
    const IPAddress& ip,
    std::uint32_t ttl
)
{
    std::size_t rdLengthOffset = 0;

    if (!mdnsAppendRecordHeader(
            buffer, capacity, length, hostName, 1, true, ttl, rdLengthOffset))
        return false;

    const std::size_t rdataStart = length;
    if (length + 4 > capacity) return false;

    buffer[length++] = ip[0];
    buffer[length++] = ip[1];
    buffer[length++] = ip[2];
    buffer[length++] = ip[3];

    mdnsPatchRdLength(buffer, rdLengthOffset, rdataStart, length);
    return true;
}

static bool mdnsAppendPtrRecord(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    const char* owner,
    const char* target,
    std::uint32_t ttl
)
{
    std::size_t rdLengthOffset = 0;

    if (!mdnsAppendRecordHeader(
            buffer, capacity, length, owner, 12, false, ttl, rdLengthOffset))
        return false;

    const std::size_t rdataStart = length;
    if (!mdnsAppendName(buffer, capacity, length, target)) return false;

    mdnsPatchRdLength(buffer, rdLengthOffset, rdataStart, length);
    return true;
}

static bool mdnsAppendSrvRecord(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    const char* owner,
    const char* hostName,
    std::uint16_t port,
    std::uint32_t ttl
)
{
    std::size_t rdLengthOffset = 0;

    if (!mdnsAppendRecordHeader(
            buffer, capacity, length, owner, 33, true, ttl, rdLengthOffset))
        return false;

    const std::size_t rdataStart = length;

    if (
        !mdnsAppendU16(buffer, capacity, length, 0) ||
        !mdnsAppendU16(buffer, capacity, length, 0) ||
        !mdnsAppendU16(buffer, capacity, length, port) ||
        !mdnsAppendName(buffer, capacity, length, hostName)
    )
        return false;

    mdnsPatchRdLength(buffer, rdLengthOffset, rdataStart, length);
    return true;
}

static bool mdnsAppendTxtRecord(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    const char* owner,
    std::uint32_t ttl
)
{
    std::size_t rdLengthOffset = 0;

    if (!mdnsAppendRecordHeader(
            buffer, capacity, length, owner, 16, true, ttl, rdLengthOffset))
        return false;

    const std::size_t rdataStart = length;
    const String service = F("service=SwitchNet");
    const String version = String(F("version=")) + SWITCHNET_VERSION;
    const String items[] = {service, version};

    for (const String& item : items)
    {
        const std::size_t itemLength = item.length();
        if (itemLength > 255 || length + 1 + itemLength > capacity)
            return false;

        buffer[length++] = static_cast<std::uint8_t>(itemLength);
        std::memcpy(buffer + length, item.c_str(), itemLength);
        length += itemLength;
    }

    mdnsPatchRdLength(buffer, rdLengthOffset, rdataStart, length);
    return true;
}

static bool mdnsBeginResponse(
    std::uint8_t* buffer,
    std::size_t capacity,
    std::size_t& length,
    std::uint16_t answerCount
)
{
    length = 0;

    return
        mdnsAppendU16(buffer, capacity, length, 0) &&
        mdnsAppendU16(buffer, capacity, length, 0x8400) &&
        mdnsAppendU16(buffer, capacity, length, 0) &&
        mdnsAppendU16(buffer, capacity, length, answerCount) &&
        mdnsAppendU16(buffer, capacity, length, 0) &&
        mdnsAppendU16(buffer, capacity, length, 0);
}

bool DiscoveryService::sendMdnsPacket(
    const std::uint8_t* data,
    std::size_t length
)
{
    if (mdnsSocket_ < 0 || data == nullptr || length == 0)
        return false;

    sockaddr_in destination{};
    destination.sin_family = AF_INET;
    destination.sin_port = htons(MDNS_PORT);
    destination.sin_addr.s_addr = inet_addr("224.0.0.251");

    const int sent = ::sendto(
        mdnsSocket_,
        data,
        length,
        0,
        reinterpret_cast<sockaddr*>(&destination),
        sizeof(destination)
    );

    if (sent != static_cast<int>(length))
    {
        ++mdnsErrors_;
        return false;
    }

    ++mdnsResponses_;
    return true;
}

void DiscoveryService::sendMdnsHostResponse()
{
    std::uint8_t packet[384] = {};
    std::size_t length = 0;

    char hostName[48] = {};
    std::snprintf(hostName, sizeof(hostName), "%s.local", hostname_);

    if (
        !mdnsBeginResponse(packet, sizeof(packet), length, 1) ||
        !mdnsAppendARecord(
            packet, sizeof(packet), length,
            hostName, WiFi.localIP(), MDNS_TTL_SECONDS)
    )
    {
        ++mdnsErrors_;
        return;
    }

    sendMdnsPacket(packet, length);
}

void DiscoveryService::sendMdnsServiceResponse()
{
    std::uint8_t packet[768] = {};
    std::size_t length = 0;

    char hostName[48] = {};
    std::snprintf(hostName, sizeof(hostName), "%s.local", hostname_);

    static constexpr char serviceName[] = "_http._tcp.local";
    static constexpr char instanceName[] = "SwitchNet._http._tcp.local";

    if (
        !mdnsBeginResponse(packet, sizeof(packet), length, 4) ||
        !mdnsAppendPtrRecord(
            packet, sizeof(packet), length,
            serviceName, instanceName, MDNS_TTL_SECONDS) ||
        !mdnsAppendSrvRecord(
            packet, sizeof(packet), length,
            instanceName, hostName, 80, MDNS_TTL_SECONDS) ||
        !mdnsAppendTxtRecord(
            packet, sizeof(packet), length,
            instanceName, MDNS_TTL_SECONDS) ||
        !mdnsAppendARecord(
            packet, sizeof(packet), length,
            hostName, WiFi.localIP(), MDNS_TTL_SECONDS)
    )
    {
        ++mdnsErrors_;
        return;
    }

    sendMdnsPacket(packet, length);
}

void DiscoveryService::sendMdnsServiceEnumerationResponse()
{
    std::uint8_t packet[384] = {};
    std::size_t length = 0;

    static constexpr char enumerationName[] =
        "_services._dns-sd._udp.local";
    static constexpr char serviceName[] =
        "_http._tcp.local";

    if (
        !mdnsBeginResponse(packet, sizeof(packet), length, 1) ||
        !mdnsAppendPtrRecord(
            packet, sizeof(packet), length,
            enumerationName, serviceName, MDNS_TTL_SECONDS)
    )
    {
        ++mdnsErrors_;
        return;
    }

    sendMdnsPacket(packet, length);
}

void DiscoveryService::sendMdnsAnnouncement(std::uint32_t ttl)
{
    std::uint8_t packet[768] = {};
    std::size_t length = 0;

    char hostName[48] = {};
    std::snprintf(hostName, sizeof(hostName), "%s.local", hostname_);

    static constexpr char serviceName[] = "_http._tcp.local";
    static constexpr char instanceName[] = "SwitchNet._http._tcp.local";

    if (
        !mdnsBeginResponse(packet, sizeof(packet), length, 4) ||
        !mdnsAppendPtrRecord(
            packet, sizeof(packet), length,
            serviceName, instanceName, ttl) ||
        !mdnsAppendSrvRecord(
            packet, sizeof(packet), length,
            instanceName, hostName, 80, ttl) ||
        !mdnsAppendTxtRecord(
            packet, sizeof(packet), length,
            instanceName, ttl) ||
        !mdnsAppendARecord(
            packet, sizeof(packet), length,
            hostName, WiFi.localIP(), ttl)
    )
    {
        ++mdnsErrors_;
        return;
    }

    if (sendMdnsPacket(packet, length))
        lastAnnouncementAt_ = millis();
}

bool DiscoveryService::readDnsName(
    const std::uint8_t* packet,
    std::size_t packetLength,
    std::size_t& offset,
    char* output,
    std::size_t outputSize
)
{
    if (
        packet == nullptr ||
        output == nullptr ||
        outputSize == 0 ||
        offset >= packetLength
    )
        return false;

    std::size_t cursor = offset;
    std::size_t written = 0;
    bool jumped = false;
    std::size_t resumeOffset = offset;
    std::uint8_t pointerDepth = 0;

    while (cursor < packetLength)
    {
        const std::uint8_t labelLength = packet[cursor];

        if ((labelLength & 0xC0U) == 0xC0U)
        {
            if (cursor + 1 >= packetLength || ++pointerDepth > 8)
                return false;

            const std::size_t pointer =
                static_cast<std::size_t>(
                    ((labelLength & 0x3FU) << 8) |
                    packet[cursor + 1]
                );

            if (pointer >= packetLength) return false;

            if (!jumped)
            {
                resumeOffset = cursor + 2;
                jumped = true;
            }

            cursor = pointer;
            continue;
        }

        ++cursor;

        if (labelLength == 0)
        {
            offset = jumped ? resumeOffset : cursor;
            if (written >= outputSize) return false;
            output[written] = '\0';
            return true;
        }

        if (
            labelLength > 63 ||
            cursor + labelLength > packetLength
        )
            return false;

        if (written > 0)
        {
            if (written + 1 >= outputSize) return false;
            output[written++] = '.';
        }

        if (written + labelLength >= outputSize) return false;

        for (std::size_t i = 0; i < labelLength; ++i)
        {
            output[written++] =
                static_cast<char>(
                    std::tolower(
                        static_cast<unsigned char>(
                            packet[cursor + i]
                        )
                    )
                );
        }

        cursor += labelLength;
    }

    return false;
}

bool DiscoveryService::dnsNameEquals(
    const char* lhs,
    const char* rhs
)
{
    if (lhs == nullptr || rhs == nullptr) return false;

    while (*lhs != '\0' && *rhs != '\0')
    {
        if (
            std::tolower(static_cast<unsigned char>(*lhs)) !=
            std::tolower(static_cast<unsigned char>(*rhs))
        )
            return false;

        ++lhs;
        ++rhs;
    }

    return *lhs == '\0' && *rhs == '\0';
}

void DiscoveryService::handleMdnsQueries()
{
    if (mdnsSocket_ < 0) return;

    // Hard realtime boundary: never process more than four mDNS datagrams
    // during one main-loop iteration.
    for (int packetIndex = 0; packetIndex < 4; ++packetIndex)
    {
        std::uint8_t packet[768] = {};
        sockaddr_in source{};
        socklen_t sourceLength = sizeof(source);

        const int received = ::recvfrom(
            mdnsSocket_,
            packet,
            sizeof(packet),
            MSG_DONTWAIT,
            reinterpret_cast<sockaddr*>(&source),
            &sourceLength
        );

        if (received < 0)
        {
            if (errno == EAGAIN || errno == EWOULDBLOCK)
                return;

            ++mdnsErrors_;
            ++mdnsRestarts_;
            stopMdnsResponder(false);
            lastMdnsRetryAt_ = millis();
            return;
        }

        if (received < 12) continue;

        ++mdnsQueries_;

        const std::uint16_t flags =
            static_cast<std::uint16_t>(
                (packet[2] << 8) | packet[3]
            );

        if ((flags & 0x8000U) != 0) continue;

        const std::uint16_t questionCount =
            static_cast<std::uint16_t>(
                (packet[4] << 8) | packet[5]
            );

        std::size_t offset = 12;
        bool needHost = false;
        bool needService = false;
        bool needEnumeration = false;

        char hostName[48] = {};
        std::snprintf(hostName, sizeof(hostName), "%s.local", hostname_);

        static constexpr char serviceName[] = "_http._tcp.local";
        static constexpr char instanceName[] = "switchnet._http._tcp.local";
        static constexpr char enumerationName[] =
            "_services._dns-sd._udp.local";

        for (
            std::uint16_t question = 0;
            question < questionCount &&
            offset < static_cast<std::size_t>(received);
            ++question
        )
        {
            char name[128] = {};

            if (
                !readDnsName(
                    packet,
                    static_cast<std::size_t>(received),
                    offset,
                    name,
                    sizeof(name)
                ) ||
                offset + 4 > static_cast<std::size_t>(received)
            )
                break;

            const std::uint16_t type =
                static_cast<std::uint16_t>(
                    (packet[offset] << 8) |
                    packet[offset + 1]
                );

            const std::uint16_t qclass =
                static_cast<std::uint16_t>(
                    ((packet[offset + 2] << 8) |
                     packet[offset + 3]) &
                    0x7FFFU
                );

            offset += 4;

            if (qclass != 1 && qclass != 255) continue;

            if (
                dnsNameEquals(name, hostName) &&
                (type == 1 || type == 255)
            )
                needHost = true;

            if (
                (
                    dnsNameEquals(name, serviceName) &&
                    (type == 12 || type == 255)
                ) ||
                (
                    dnsNameEquals(name, instanceName) &&
                    (type == 16 || type == 33 || type == 255)
                )
            )
                needService = true;

            if (
                dnsNameEquals(name, enumerationName) &&
                (type == 12 || type == 255)
            )
                needEnumeration = true;
        }

        if (needHost) sendMdnsHostResponse();
        if (needService) sendMdnsServiceResponse();
        if (needEnumeration) sendMdnsServiceEnumerationResponse();
    }
}

void DiscoveryService::handleUdpDiscovery()
{
    const int packetSize = udp_.parsePacket();

    if (packetSize <= 0)
    {
        return;
    }

    char buffer[64] = {};
    const int readLength = udp_.read(
        buffer,
        sizeof(buffer) - 1
    );

    if (readLength <= 0)
    {
        return;
    }

    buffer[readLength] = '\0';

    if (std::strcmp(buffer, DISCOVERY_MAGIC) != 0)
    {
        return;
    }

    ++requests_;

    String response = F("SWITCHNET_HERE_V1|");
    response += WiFi.localIP().toString();
    response += '|';
    response += hostname_;
    response += F(".local|");
    response += SWITCHNET_VERSION;
    response += '|';
    response += config_.udpPort;

    udp_.beginPacket(
        udp_.remoteIP(),
        udp_.remotePort()
    );
    udp_.write(
        reinterpret_cast<const std::uint8_t*>(
            response.c_str()
        ),
        response.length()
    );
    udp_.endPacket();
}


void DiscoveryService::normalizeHostname(
    const char* input,
    char* output,
    std::size_t outputSize
)
{
    if (output == nullptr || outputSize == 0)
    {
        return;
    }

    std::size_t written = 0;

    if (input != nullptr)
    {
        for (
            std::size_t i = 0;
            input[i] != '\0' &&
            written + 1 < outputSize;
            ++i
        )
        {
            const unsigned char ch =
                static_cast<unsigned char>(input[i]);

            if (std::isalnum(ch))
            {
                output[written++] =
                    static_cast<char>(std::tolower(ch));
            }
            else if (
                (ch == '-' || ch == '_') &&
                written > 0
            )
            {
                output[written++] = '-';
            }
        }
    }

    while (
        written > 0 &&
        output[written - 1] == '-'
    )
    {
        --written;
    }

    if (written == 0)
    {
        static constexpr char fallback[] = "switchnet";
        const std::size_t count =
            sizeof(fallback) - 1 < outputSize - 1
                ? sizeof(fallback) - 1
                : outputSize - 1;

        std::memcpy(output, fallback, count);
        written = count;
    }

    output[written] = '\0';
}
