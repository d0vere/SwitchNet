#pragma once

#include <WebServer.h>

#include <cstddef>

#include "AutoWakeManager.h"
#include "Config.h"
#include "DiscoveryService.h"
#include "IControllerBackend.h"
#include "Storage.h"
#include "Switch2WakeBoot.h"
#include "UdpServer.h"
#include "WifiManager.h"

class HttpServer
{
public:
    HttpServer(
        Storage& storage,
        WifiManager& wifi,
        UdpServer& udp,
        IControllerBackend& backend,
        Switch2WakeBoot& wake,
        AutoWakeManager& autoWake,
        DiscoveryService& discovery,
        Config& config
    );

    void begin();
    void update();

    bool otaInProgress() const;
    const String& otaLastError() const;

private:
    static constexpr std::uint16_t HTTP_PORT = 80;
    static constexpr std::uint32_t HTTP_SERVICE_INTERVAL_MS = 4;

    ::WebServer server_{HTTP_PORT};

    Storage& storage_;
    WifiManager& wifi_;
    UdpServer& udp_;
    IControllerBackend& backend_;
    Switch2WakeBoot& wake_;
    AutoWakeManager& autoWake_;
    DiscoveryService& discovery_;
    Config& config_;

    bool rebootPending_ = false;
    std::uint32_t rebootAt_ = 0;
    std::uint32_t lastHttpServiceAt_ = 0;

    bool otaInProgress_ = false;
    bool otaSuccess_ = false;
    bool otaFailed_ = false;
    std::size_t otaBytesWritten_ = 0;
    std::uint8_t otaErrorCode_ = 0;
    String otaError_;

    void configureRoutes();

    void handleRoot();
    void handleNetworkPage();
    void handleWifiScanApi();
    void handleSaveWifi();
    void handleStatusApi();
    void handleGetConfigApi();
    void handleSaveConfigApi();
    void handleRumbleApi();
    void handleWakeApi();
    void handleWakeCaptureApi();
    void handleWakeClearApi();
    void handleAutoWakeApi();
    void handleDualUsbLabApi();
    void handleApiRoutes();
    void handleOtaComplete();
    void handleOtaUpload();
    void handleNotFound();

    void scheduleReboot(std::uint32_t delayMs);

    String buildConfigurationPage() const;
    String buildNetworkPage() const;
    static const char* wifiAuthName(wifi_auth_mode_t auth);
    String buildStatusPage() const;
    String buildStatusJson() const;
    String buildConfigJson() const;
    String buildApiRoutesJson() const;

    static String htmlEscape(const String& value);
    static String jsonEscape(const String& value);
};
