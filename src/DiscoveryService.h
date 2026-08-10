#pragma once

#include <Arduino.h>
#include <WiFiUdp.h>
#include <cstddef>

#include <cstdint>

#include "Config.h"
#include "WifiManager.h"

class DiscoveryService
{
public:
    DiscoveryService(
        WifiManager& wifi,
        const Config& config
    );

    void begin();
    void update();

    bool mdnsReady() const;
    bool udpReady() const;
    std::uint32_t requests() const;
    std::uint32_t mdnsQueries() const;
    std::uint32_t mdnsResponses() const;
    std::uint32_t mdnsRestarts() const;
    std::uint32_t mdnsErrors() const;
    const char* hostname() const;

private:
    static constexpr std::uint16_t DISCOVERY_PORT = 5455;
    static constexpr const char* DISCOVERY_MAGIC =
        "SWITCHNET_DISCOVER_V1";

    WifiManager& wifi_;
    const Config& config_;

    WiFiUDP udp_;

    bool mdnsReady_ = false;
    bool udpReady_ = false;
    bool wasConnected_ = false;

    int mdnsSocket_ = -1;
    std::uint32_t lastIp_ = 0;
    std::uint32_t lastMdnsRetryAt_ = 0;
    std::uint32_t lastAnnouncementAt_ = 0;
    std::uint32_t nextBurstAnnouncementAt_ = 0;
    std::uint8_t announcementBurstRemaining_ = 0;

    std::uint32_t requests_ = 0;
    std::uint32_t mdnsQueries_ = 0;
    std::uint32_t mdnsResponses_ = 0;
    std::uint32_t mdnsRestarts_ = 0;
    std::uint32_t mdnsErrors_ = 0;
    char hostname_[32] = "switchnet";

    static constexpr std::uint16_t MDNS_PORT = 5353;
    static constexpr std::uint32_t MDNS_TTL_SECONDS = 120;
    static constexpr std::uint32_t MDNS_RETRY_MS = 5000;
    static constexpr std::uint32_t MDNS_ANNOUNCE_INTERVAL_MS = 60000;

    void startNetworkServices();
    void stopNetworkServices();
    void handleUdpDiscovery();

    bool startMdnsResponder();
    void stopMdnsResponder(bool goodbye = false);
    void maintainMdnsResponder();
    void handleMdnsQueries();
    void sendMdnsAnnouncement(std::uint32_t ttl = MDNS_TTL_SECONDS);
    void sendMdnsHostResponse();
    void sendMdnsServiceResponse();
    void sendMdnsServiceEnumerationResponse();

    bool sendMdnsPacket(
        const std::uint8_t* data,
        std::size_t length
    );

    static bool readDnsName(
        const std::uint8_t* packet,
        std::size_t packetLength,
        std::size_t& offset,
        char* output,
        std::size_t outputSize
    );

    static bool dnsNameEquals(
        const char* lhs,
        const char* rhs
    );

    static void normalizeHostname(
        const char* input,
        char* output,
        std::size_t outputSize
    );
};
