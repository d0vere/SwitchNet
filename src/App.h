#pragma once

#include "AutoWakeManager.h"
#include "Config.h"
#include "DiscoveryService.h"
#include "HttpServer.h"
#include "NintendoProControllerBackend.h"
#include "Storage.h"
#include "Switch2WakeBoot.h"
#include "UdpServer.h"
#include "WifiManager.h"

class App
{
public:
    App();

    void begin();
    void update();

private:
    Config config_{};

    Storage storage_;
    Switch2WakeBoot wake_;
    WifiManager wifi_;
    NintendoProControllerBackend backend_;
    UdpServer udp_;
    AutoWakeManager autoWake_;
    DiscoveryService discovery_;

    HttpServer http_;
    bool specialWakeBoot_ = false;
};
