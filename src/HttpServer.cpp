#include "HttpServer.h"

#include <Arduino.h>
#include <WiFi.h>
#include <Update.h>

#include <cstring>

#include "Constants.h"
#include "Version.h"

HttpServer::HttpServer(
    Storage& storage,
    WifiManager& wifi,
    UdpServer& udp,
    IControllerBackend& backend,
    Switch2WakeBoot& wake,
    AutoWakeManager& autoWake,
    DiscoveryService& discovery,
    Config& config
)
    : storage_(storage),
      wifi_(wifi),
      udp_(udp),
      backend_(backend),
      wake_(wake),
      autoWake_(autoWake),
      discovery_(discovery),
      config_(config)
{
}

void HttpServer::begin()
{
    configureRoutes();
    server_.begin();

    Serial.println("[HTTP] Server started on port 80");
}

void HttpServer::update()
{
    const std::uint32_t now = millis();

    if (
        otaInProgress_ ||
        now - lastHttpServiceAt_ >= HTTP_SERVICE_INTERVAL_MS
    )
    {
        lastHttpServiceAt_ = now;
        server_.handleClient();
    }

    if (
        rebootPending_ &&
        static_cast<std::int32_t>(now - rebootAt_) >= 0
    )
    {
        Serial.println("[SYSTEM] Restarting...");
        Serial.flush();

        ESP.restart();
    }
}
bool HttpServer::otaInProgress() const
{
    return otaInProgress_;
}

const String& HttpServer::otaLastError() const
{
    return otaError_;
}


void HttpServer::configureRoutes()
{
    server_.on(
        "/",
        HTTP_GET,
        [this]()
        {
            handleRoot();
        }
    );

    server_.on(
        "/network",
        HTTP_GET,
        [this]()
        {
            handleNetworkPage();
        }
    );

    server_.on(
        "/api/wifi/scan",
        HTTP_GET,
        [this]()
        {
            handleWifiScanApi();
        }
    );

    server_.on(
        "/wifi",
        HTTP_POST,
        [this]()
        {
            handleSaveWifi();
        }
    );

    server_.on(
        "/api/routes",
        HTTP_GET,
        [this]()
        {
            handleApiRoutes();
        }
    );

    server_.on(
        "/api/status",
        HTTP_GET,
        [this]()
        {
            handleStatusApi();
        }
    );

    server_.on(
        "/api/config",
        HTTP_GET,
        [this]()
        {
            handleGetConfigApi();
        }
    );

    server_.on(
        "/api/config",
        HTTP_POST,
        [this]()
        {
            handleSaveConfigApi();
        }
    );

    server_.on(
        "/api/wake",
        HTTP_POST,
        [this]()
        {
            handleWakeApi();
        }
    );

    server_.on(
        "/api/wake/capture",
        HTTP_POST,
        [this]()
        {
            handleWakeCaptureApi();
        }
    );

    server_.on(
        "/api/wake/clear",
        HTTP_POST,
        [this]()
        {
            handleWakeClearApi();
        }
    );

    server_.on(
        "/api/dual-usb-lab",
        HTTP_POST,
        [this]()
        {
            handleDualUsbLabApi();
        }
    );

    server_.on(
        "/api/auto-wake",
        HTTP_POST,
        [this]()
        {
            handleAutoWakeApi();
        }
    );

    server_.on(
        "/api/rumble",
        HTTP_POST,
        [this]()
        {
            handleRumbleApi();
        }
    );

    server_.on(
        "/api/ota",
        HTTP_POST,
        [this]()
        {
            handleOtaComplete();
        },
        [this]()
        {
            handleOtaUpload();
        }
    );

    server_.onNotFound(
        [this]()
        {
            handleNotFound();
        }
    );
}

void HttpServer::handleRoot()
{
    if (wifi_.accessPointActive())
    {
        server_.send(
            200,
            "text/html; charset=utf-8",
            buildConfigurationPage()
        );

        return;
    }

    server_.send(
        200,
        "text/html; charset=utf-8",
        buildStatusPage()
    );
}

void HttpServer::handleNetworkPage()
{
    server_.send(
        200,
        "text/html; charset=utf-8",
        buildNetworkPage()
    );
}

const char* HttpServer::wifiAuthName(wifi_auth_mode_t auth)
{
    switch (auth)
    {
        case WIFI_AUTH_OPEN: return "OPEN";
        case WIFI_AUTH_WEP: return "WEP";
        case WIFI_AUTH_WPA_PSK: return "WPA-PSK";
        case WIFI_AUTH_WPA2_PSK: return "WPA2-PSK";
        case WIFI_AUTH_WPA_WPA2_PSK: return "WPA/WPA2-PSK";
        case WIFI_AUTH_WPA2_ENTERPRISE: return "WPA2-Enterprise";
#ifdef WIFI_AUTH_WPA3_PSK
        case WIFI_AUTH_WPA3_PSK: return "WPA3-SAE";
#endif
#ifdef WIFI_AUTH_WPA2_WPA3_PSK
        case WIFI_AUTH_WPA2_WPA3_PSK: return "WPA2/WPA3";
#endif
#ifdef WIFI_AUTH_WAPI_PSK
        case WIFI_AUTH_WAPI_PSK: return "WAPI";
#endif
        default: return "UNKNOWN";
    }
}

void HttpServer::handleWifiScanApi()
{
    /*
     * Asynchronous scan: do not block handleClient() for several seconds.
     * The browser starts the scan and then polls until the ESP32
     * restituisce i risultati.
     */
    int result = WiFi.scanComplete();

    if (result == WIFI_SCAN_FAILED)
    {
        WiFi.scanDelete();
        WiFi.scanNetworks(true, true, false, 300);
        server_.send(
            202,
            "application/json",
            R"JSON({"state":"scanning","networks":[]})JSON"
        );
        return;
    }

    if (result == WIFI_SCAN_RUNNING)
    {
        server_.send(
            202,
            "application/json",
            R"JSON({"state":"scanning","networks":[]})JSON"
        );
        return;
    }

    String json;
    json.reserve(512 + result * 150);
    json += F("{\"state\":\"done\",\"networks\":[");

    // Remove duplicate SSIDs while keeping the instance with the strongest signal.
    bool first = true;
    for (int i = 0; i < result; ++i)
    {
        const String ssid = WiFi.SSID(i);
        if (ssid.isEmpty())
        {
            continue;
        }

        bool duplicate = false;
        for (int j = 0; j < i; ++j)
        {
            if (WiFi.SSID(j) == ssid && WiFi.RSSI(j) >= WiFi.RSSI(i))
            {
                duplicate = true;
                break;
            }
        }
        if (duplicate)
        {
            continue;
        }

        if (!first)
        {
            json += ',';
        }
        first = false;

        const int32_t rssi = WiFi.RSSI(i);
        const wifi_auth_mode_t auth = WiFi.encryptionType(i);

        json += F("{\"ssid\":\"");
        json += jsonEscape(ssid);
        json += F("\",\"rssi\":");
        json += String(rssi);
        json += F(",\"channel\":");
        json += String(WiFi.channel(i));
        json += F(",\"security\":\"");
        json += wifiAuthName(auth);
        json += F("\",\"open\":");
        json += auth == WIFI_AUTH_OPEN ? F("true") : F("false");
        json += '}';
    }

    json += F("]}");
    WiFi.scanDelete();
    server_.send(200, "application/json", json);
}

void HttpServer::handleSaveWifi()
{
    if (!server_.hasArg("ssid"))
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"missing_ssid"})JSON"
        );

        return;
    }

    String ssid = server_.arg("ssid");
    String password = server_.arg("password");
    String hostname = server_.arg("hostname");
    const bool keepExistingPassword =
        password.isEmpty() && config_.password[0] != '\0';

    ssid.trim();
    hostname.trim();

    if (ssid.isEmpty())
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"empty_ssid"})JSON"
        );

        return;
    }

    if (ssid.length() > 32)
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"ssid_too_long"})JSON"
        );

        return;
    }

    if (password.length() > 64)
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"password_too_long"})JSON"
        );

        return;
    }

    if (hostname.isEmpty())
    {
        hostname = HOSTNAME;
    }

    if (hostname.length() > 31)
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"hostname_too_long"})JSON"
        );

        return;
    }

    std::memset(config_.ssid, 0, sizeof(config_.ssid));
    if (!keepExistingPassword)
    {
        std::memset(config_.password, 0, sizeof(config_.password));
    }
    std::memset(config_.hostname, 0, sizeof(config_.hostname));

    std::strncpy(
        config_.ssid,
        ssid.c_str(),
        sizeof(config_.ssid) - 1
    );

    if (!keepExistingPassword)
    {
        std::strncpy(
            config_.password,
            password.c_str(),
            sizeof(config_.password) - 1
        );
    }

    std::strncpy(
        config_.hostname,
        hostname.c_str(),
        sizeof(config_.hostname) - 1
    );

    config_.udpPort = UDP_PORT;

    if (!storage_.save(config_))
    {
        Serial.println("[CONFIG] Failed to save WiFi configuration");

        server_.send(
            500,
            "application/json",
            R"JSON({"error":"storage_failure"})JSON"
        );

        return;
    }

    Serial.println("[CONFIG] WiFi configuration saved");

    static constexpr char successPage[] = R"HTML(
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1">

    <title>SwitchNet</title>

    <style>
        :root {
            color-scheme: dark;
            font-family: system-ui, sans-serif;
        }

        body {
            max-width: 640px;
            margin: 0 auto;
            padding: 32px 20px;
            background: #101217;
            color: #f4f4f5;
        }

        .card {
            padding: 24px;
            background: #1a1d24;
            border: 1px solid #30343d;
            border-radius: 16px;
        }

        .ok {
            color: #70e39e;
        }
    </style>
</head>

<body>
    <main class="card">
        <h1>SwitchNet</h1>
        <h2 class="ok">Configuration saved</h2>

        <p>
            The device will restart and validate the configured network.
            If the connection fails, the SwitchNet Setup access point remains available.
        </p>

        <p>
            You can close this page.
        </p>
    </main>
</body>
</html>
)HTML";

    server_.send(
        200,
        "text/html; charset=utf-8",
        successPage
    );

    scheduleReboot(1500);
}

void HttpServer::handleStatusApi()
{
    server_.send(
        200,
        "application/json",
        buildStatusJson()
    );
}


void HttpServer::handleGetConfigApi()
{
    server_.send(
        200,
        "application/json",
        buildConfigJson()
    );
}

void HttpServer::handleSaveConfigApi()
{
    if (!server_.hasArg("hostname") ||
        !server_.hasArg("udp_port") ||
        !server_.hasArg("controller_mode"))
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"missing_configuration_field"})JSON"
        );
        return;
    }

    String hostname = server_.arg("hostname");
    String portText = server_.arg("udp_port");
    String controllerMode = server_.arg("controller_mode");

    hostname.trim();
    portText.trim();
    controllerMode.trim();

    if (hostname.isEmpty() || hostname.length() > 31)
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"invalid_hostname"})JSON"
        );
        return;
    }

    const long parsedPort = portText.toInt();
    if (parsedPort < 1024 || parsedPort > 65535)
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"invalid_udp_port"})JSON"
        );
        return;
    }

    EmulatedController parsedController;
    if (!parseEmulatedController(controllerMode.c_str(), parsedController))
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"error":"unsupported_controller_mode"})JSON"
        );
        return;
    }

    std::memset(config_.hostname, 0, sizeof(config_.hostname));
    std::strncpy(
        config_.hostname,
        hostname.c_str(),
        sizeof(config_.hostname) - 1
    );
    config_.udpPort = static_cast<std::uint16_t>(parsedPort);
    config_.emulatedController = parsedController;
    const bool requestedRumble = server_.hasArg("rumble_enabled");
    udp_.applyRumbleEnabled(requestedRumble);

    if (!storage_.saveRuntimeConfig(config_))
    {
        server_.send(
            500,
            "application/json",
            R"JSON({"error":"storage_failure"})JSON"
        );
        return;
    }

    server_.send(
        200,
        "application/json",
        R"JSON({"ok":true,"rebooting":true})JSON"
    );

    scheduleReboot(1200);
}

void HttpServer::handleWakeApi()
{
    if (!wake_.requestLiveWake())
    {
        String response = F("{\"ok\":false,\"error\":\"");
        response += jsonEscape(wake_.lastState());
        response += F("\"}");

        server_.send(
            409,
            "application/json",
            response
        );
        return;
    }

    server_.send(
        202,
        "application/json",
        R"JSON({"ok":true,"rebooting":false,"mode":"live_wake"})JSON"
    );
}

void HttpServer::handleWakeCaptureApi()
{
    if (!wake_.scheduleCapture())
    {
        server_.send(
            500,
            "application/json",
            R"JSON({"ok":false,"error":"capture_schedule_failed"})JSON"
        );
        return;
    }

    server_.send(
        202,
        "application/json",
        R"JSON({"ok":true,"rebooting":true,"mode":"capture","timeout_seconds":60})JSON"
    );
    scheduleReboot(450);
}

void HttpServer::handleWakeClearApi()
{
    const bool cleared = wake_.clearIdentity();

    String response = F("{\"ok\":true,\"cleared\":");
    response += cleared ? F("true") : F("false");
    response += '}';

    server_.send(200, "application/json", response);
}

void HttpServer::handleDualUsbLabApi()
{
    server_.send(
        200,
        "application/json",
        R"JSON({"ok":true,"deprecated":true,"mode":"dynamic_dual_always_enabled","rebooting":false})JSON"
    );
}

void HttpServer::handleAutoWakeApi()
{
    if (!server_.hasArg("enabled"))
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"ok":false,"error":"missing_enabled"})JSON"
        );
        return;
    }

    String value = server_.arg("enabled");
    value.trim();
    value.toLowerCase();

    bool enabled = false;

    if (value == "1" || value == "true" || value == "on")
    {
        enabled = true;
    }
    else if (value == "0" || value == "false" || value == "off")
    {
        enabled = false;
    }
    else
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"ok":false,"error":"invalid_enabled"})JSON"
        );
        return;
    }

    const bool previous = config_.autoWakeEnabled;
    autoWake_.setEnabled(enabled);

    if (!storage_.saveRuntimeConfig(config_))
    {
        autoWake_.setEnabled(previous);

        server_.send(
            500,
            "application/json",
            R"JSON({"ok":false,"error":"storage_failure"})JSON"
        );
        return;
    }

    String response = F("{\"ok\":true,\"auto_wake_enabled\":");
    response += config_.autoWakeEnabled ? F("true") : F("false");
    response += F(",\"rebooting\":false}");

    server_.send(200, "application/json", response);
}

void HttpServer::handleApiRoutes()
{
    server_.send(
        200,
        "application/json",
        buildApiRoutesJson()
    );
}

void HttpServer::handleRumbleApi()
{
    if (!server_.hasArg("enabled") && !server_.hasArg("intensity"))
    {
        server_.send(
            400,
            "application/json",
            R"JSON({"ok":false,"error":"missing_parameter"})JSON"
        );
        return;
    }

    const bool previousEnabled = config_.rumbleEnabled;
    const std::uint8_t previousIntensity = config_.rumbleIntensity;

    if (server_.hasArg("enabled"))
    {
        String value = server_.arg("enabled");
        value.trim();
        value.toLowerCase();

        bool enabled = false;
        if (value == "1" || value == "true" || value == "on")
        {
            enabled = true;
        }
        else if (value == "0" || value == "false" || value == "off")
        {
            enabled = false;
        }
        else
        {
            server_.send(
                400,
                "application/json",
                R"JSON({"ok":false,"error":"invalid_enabled"})JSON"
            );
            return;
        }

        udp_.applyRumbleEnabled(enabled);
    }

    if (server_.hasArg("intensity"))
    {
        const int intensity = server_.arg("intensity").toInt();
        if (intensity < 0 || intensity > 100)
        {
            udp_.applyRumbleEnabled(previousEnabled);
            server_.send(
                400,
                "application/json",
                R"JSON({"ok":false,"error":"invalid_intensity"})JSON"
            );
            return;
        }

        udp_.applyRumbleIntensity(
            static_cast<std::uint8_t>(intensity)
        );
    }

    if (!storage_.saveRuntimeConfig(config_))
    {
        udp_.applyRumbleIntensity(previousIntensity);
        udp_.applyRumbleEnabled(previousEnabled);

        server_.send(
            500,
            "application/json",
            R"JSON({"ok":false,"error":"storage_failure"})JSON"
        );
        return;
    }

    String response = F("{\"ok\":true,\"rumble_enabled\":");
    response += config_.rumbleEnabled ? F("true") : F("false");
    response += F(",\"rumble_intensity\":");
    response += String(config_.rumbleIntensity);
    response += F(",\"rebooting\":false}");

    server_.send(200, "application/json", response);
}

void HttpServer::handleOtaComplete()
{
    if (wifi_.accessPointActive())
    {
        server_.send(
            403,
            "application/json",
            R"JSON({"ok":false,"error":"ota_disabled_in_setup_ap"})JSON"
        );
        return;
    }

    if (otaSuccess_ && !otaFailed_)
    {
        String json;
        json.reserve(160);
        json += F("{\"ok\":true,\"bytes\":");
        json += String(otaBytesWritten_);
        json += F(",\"rebooting\":true}");

        server_.send(200, "application/json", json);
        scheduleReboot(900);
        return;
    }

    String json;
    json.reserve(256);
    json += F("{\"ok\":false,\"error\":\"");
    json += jsonEscape(
        otaError_.isEmpty()
            ? String("ota_failed")
            : otaError_
    );
    json += F("\",\"code\":");
    json += String(otaErrorCode_);
    json += F(",\"bytes\":");
    json += String(otaBytesWritten_);
    json += F("}");
    server_.send(500, "application/json", json);
}

void HttpServer::handleOtaUpload()
{
    HTTPUpload& upload = server_.upload();

    if (wifi_.accessPointActive())
    {
        otaFailed_ = true;
        otaError_ = F("ota_disabled_in_setup_ap");
        return;
    }

    switch (upload.status)
    {
        case UPLOAD_FILE_START:
        {
            otaInProgress_ = true;
            otaSuccess_ = false;
            otaFailed_ = false;
            otaBytesWritten_ = 0;
            otaErrorCode_ = 0;
            otaError_ = "";

            if (!upload.filename.endsWith(".bin"))
            {
                otaFailed_ = true;
                otaError_ = F("firmware_must_be_bin");
                return;
            }

            // Stop forwarding live input before flash writes begin. The USB
            // personality remains mounted but transitions to a neutral state.
            backend_.setSourceConnected(false);
            backend_.reset();

            const std::size_t available =
                ESP.getFreeSketchSpace();

            if (
                available == 0 ||
                !Update.begin(available, U_FLASH)
            )
            {
                otaFailed_ = true;
                otaErrorCode_ =
                    static_cast<std::uint8_t>(
                        Update.getError()
                    );
                otaError_ = Update.errorString();
                return;
            }

            break;
        }

        case UPLOAD_FILE_WRITE:
        {
            if (otaFailed_)
            {
                return;
            }

            const std::size_t written = Update.write(
                upload.buf,
                upload.currentSize
            );

            otaBytesWritten_ += written;
            delay(0);

            if (written != upload.currentSize)
            {
                otaFailed_ = true;
                otaErrorCode_ =
                    static_cast<std::uint8_t>(
                        Update.getError()
                    );
                otaError_ = Update.errorString();
                if (Update.isRunning())
                {
                    Update.abort();
                }
            }

            break;
        }

        case UPLOAD_FILE_END:
        {
            if (!otaFailed_)
            {
                if (Update.end(true))
                {
                    otaSuccess_ = true;
                }
                else
                {
                    otaFailed_ = true;
                    otaErrorCode_ =
                        static_cast<std::uint8_t>(
                            Update.getError()
                        );
                    otaError_ = Update.errorString();
                    if (Update.isRunning())
                    {
                        Update.abort();
                    }
                }
            }
            else if (Update.isRunning())
            {
                Update.abort();
            }

            otaInProgress_ = false;
            break;
        }

        case UPLOAD_FILE_ABORTED:
        {
            if (Update.isRunning())
            {
                Update.abort();
            }
            otaFailed_ = true;
            otaSuccess_ = false;
            otaInProgress_ = false;
            otaError_ = F("upload_aborted");
            break;
        }

        default:
            break;
    }
}

void HttpServer::handleNotFound()
{
    server_.send(
        404,
        "application/json",
        R"JSON({"error":"not_found"})JSON"
    );
}

void HttpServer::scheduleReboot(std::uint32_t delayMs)
{
    rebootPending_ = true;
    rebootAt_ = millis() + delayMs;
}

String HttpServer::buildConfigurationPage() const
{
    String page;
    page.reserve(9000);

    page += F(R"HTML(
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SwitchNet Setup</title>
<style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;--bg:#0d1015;--panel:#171b22;--panel2:#10141a;--border:#2a303a;--text:#f4f6f8;--muted:#929baa;--accent:#558cff;--ok:#65df9a;--warn:#f4c36a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text)}main{max-width:760px;margin:auto;padding:28px 18px}.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:22px;margin-bottom:16px}h1,h2{margin-top:0}.muted{color:var(--muted)}label{display:block;margin:17px 0 6px;color:var(--muted);font-size:.85rem}input{width:100%;padding:11px;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:9px;font:inherit}button{display:block;width:100%;padding:12px;margin-top:14px;border:0;border-radius:9px;background:var(--accent);color:white;font:inherit;font-weight:700;cursor:pointer}.nets{display:grid;gap:8px;margin-top:12px}.net{display:grid;grid-template-columns:1fr auto;gap:5px 12px;padding:12px;border:1px solid var(--border);border-radius:10px;background:var(--panel2);cursor:pointer}.net:hover,.net.selected{border-color:var(--accent)}.meta{color:var(--muted);font-size:.78rem}.good{color:var(--ok)}.weak{color:var(--warn)}.bad{color:#ff8585}
</style>
</head>
<body><main>
<section class="card">
<h1>SwitchNet Setup</h1>
<p class="muted">The setup access point remains available while SwitchNet validates the router connection. It is closed only after Wi-Fi connects successfully.</p>
<button type="button" id="scanBtn">Scan Wi-Fi networks</button>
<p class="muted" id="scanState">Press the button to scan for nearby networks.</p>
<div class="nets" id="networks"></div>
</section>

<section class="card">
<h2>Wi-Fi credentials</h2>
<form method="post" action="/wifi">
<label for="ssid">SSID</label>
<input id="ssid" name="ssid" type="text" maxlength="32" autocomplete="off" required>

<label for="password">Password</label>
<input id="password" name="password" type="password" maxlength="64" autocomplete="new-password">

<label for="hostname">Hostname</label>
<input id="hostname" name="hostname" type="text" maxlength="31" value=")HTML");

    page += htmlEscape(
        config_.hostname[0] != '\0'
            ? config_.hostname
            : HOSTNAME
    );

    page += F(R"HTML(">

<button type="submit">Save and validate connection</button>
</form>
<p class="muted">If the router cannot be reached, reconnect to <strong>SwitchNet Setup</strong>. The setup AP stays available during validation.</p>
</section>

<script>
const btn=document.getElementById('scanBtn');
const state=document.getElementById('scanState');
const list=document.getElementById('networks');
const ssid=document.getElementById('ssid');
let timer=null;

function esc(v){
  const e=document.createElement('div');
  e.textContent=v;
  return e.innerHTML;
}
function quality(r){
  if(r>=-60)return ['Excellent','good'];
  if(r>=-70)return ['Good','good'];
  if(r>=-80)return ['Weak','weak'];
  return ['Critical','bad'];
}
function render(nets){
  list.innerHTML='';
  if(!nets.length){
    state.textContent='No networks found.';
    return;
  }
  nets.sort((a,b)=>b.rssi-a.rssi);
  for(const n of nets){
    const q=quality(n.rssi);
    const el=document.createElement('div');
    el.className='net';
    el.innerHTML=
      '<strong>'+esc(n.ssid)+'</strong>'+
      '<span class="'+q[1]+'">'+n.rssi+' dBm</span>'+
      '<span class="meta">'+esc(n.security)+' · channel '+n.channel+'</span>'+
      '<span class="meta">'+q[0]+'</span>';
    el.onclick=()=>{
      ssid.value=n.ssid;
      document.querySelectorAll('.net').forEach(x=>x.classList.remove('selected'));
      el.classList.add('selected');
      document.getElementById('password').focus();
    };
    list.appendChild(el);
  }
  state.textContent=nets.length+' networks detected.';
}
async function poll(){
  try{
    const r=await fetch('/api/wifi/scan',{cache:'no-store'});
    const j=await r.json();
    if(j.state==='scanning'){
      state.textContent='Scanning…';
      timer=setTimeout(poll,500);
      return;
    }
    btn.disabled=false;
    render(j.networks||[]);
  }catch(e){
    btn.disabled=false;
    state.textContent='Scan error: '+e;
  }
}
btn.onclick=()=>{
  btn.disabled=true;
  list.innerHTML='';
  state.textContent='Starting scan…';
  if(timer)clearTimeout(timer);
  poll();
};
</script>
</main></body></html>
)HTML");

    return page;
}

String HttpServer::buildNetworkPage() const
{
    String page;
    page.reserve(10500);

    page += F(R"HTML(
<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SwitchNet - Wi-Fi</title>
<style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;--bg:#0d1015;--panel:#171b22;--panel2:#10141a;--border:#2a303a;--text:#f4f6f8;--muted:#929baa;--accent:#558cff;--ok:#65df9a;--warn:#f4c36a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text)}main{max-width:780px;margin:auto;padding:28px 18px}.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:22px;margin-bottom:16px}h1,h2{margin-top:0}.muted{color:var(--muted)}label{display:block;margin:17px 0 6px;color:var(--muted);font-size:.85rem}input{width:100%;padding:11px;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:9px;font:inherit}button,.link{display:block;width:100%;padding:12px;margin-top:14px;border:0;border-radius:9px;background:var(--accent);color:white;font:inherit;font-weight:700;text-align:center;text-decoration:none;cursor:pointer}.link{background:#29313d}.notice{color:var(--warn);font-size:.85rem;margin-top:14px}.current{padding:12px;background:var(--panel2);border-radius:10px;margin:16px 0}.nets{display:grid;gap:8px;margin-top:12px}.net{display:grid;grid-template-columns:1fr auto;gap:5px 12px;padding:12px;border:1px solid var(--border);border-radius:10px;background:var(--panel2);cursor:pointer}.net:hover{border-color:var(--accent)}.net strong{overflow-wrap:anywhere}.meta{color:var(--muted);font-size:.78rem}.signal{font-weight:700}.good{color:var(--ok)}.weak{color:var(--warn)}.bad{color:#ff8585}.selected{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}#scanState{min-height:1.2em}
</style></head><body><main>
<section class="card"><h1>Wi-Fi Network</h1>
<p class="muted">Select a network detected by the ESP32. The scan also shows signal strength, channel, and security.</p>
<div class="current"><span class="muted">Saved SSID</span><br><b>)HTML");
    page += htmlEscape(config_.ssid);
    page += F(R"HTML(</b></div>
<button type="button" id="scanBtn">Scan Wi-Fi networks</button>
<p class="muted" id="scanState">Press the button to scan for networks.</p>
<div class="nets" id="networks"></div>
</section>

<section class="card"><h2>Credentials</h2>
<form method="post" action="/wifi" id="wifiForm">
<label for="ssid">SSID</label>
<input id="ssid" name="ssid" type="text" maxlength="32" required value=")HTML");
    page += htmlEscape(config_.ssid);
    page += F(R"HTML(">
<label for="password">Password</label>
<input id="password" name="password" type="password" maxlength="64" autocomplete="new-password" placeholder="Leave blank to keep the current password">
<p class="muted" id="passwordHint">The saved password is never displayed.</p>
<label for="hostname">Hostname</label>
<input id="hostname" name="hostname" type="text" maxlength="31" required value=")HTML");
    page += htmlEscape(config_.hostname[0] != '\0' ? config_.hostname : HOSTNAME);
    page += F(R"HTML(">
<button type="submit">Save network and restart</button></form>
<a class="link" href="/">Back to dashboard</a>
<div class="notice">On the first connection, SwitchNet waits up to 40 seconds. If the network is unreachable, it returns to "SwitchNet Setup". For realtime controller traffic, prefer an RSSI better than about -70 dBm.</div>
</section>

<script>
const btn=document.getElementById('scanBtn'), state=document.getElementById('scanState');
const list=document.getElementById('networks'), ssid=document.getElementById('ssid');
const pass=document.getElementById('password'), hint=document.getElementById('passwordHint');
let timer=null;

function quality(r){
  if(r>=-60)return ['Excellent','good'];
  if(r>=-70)return ['Good','good'];
  if(r>=-80)return ['Weak','weak'];
  return ['Critical','bad'];
}
function esc(v){const e=document.createElement('div');e.textContent=v;return e.innerHTML}
function selectNetwork(n,el){
  ssid.value=n.ssid;
  document.querySelectorAll('.net').forEach(x=>x.classList.remove('selected'));
  el.classList.add('selected');
  if(n.open){
    pass.value='';
    pass.disabled=true;
    hint.textContent='Open network: no password required.';
  }else{
    pass.disabled=false;
    hint.textContent='Enter the password. If you select the already saved SSID, leave it blank to keep the current password.';
    pass.focus();
  }
}
function render(nets){
  list.innerHTML='';
  if(!nets.length){state.textContent='No networks found.';return}
  nets.sort((a,b)=>b.rssi-a.rssi);
  for(const n of nets){
    const q=quality(n.rssi), el=document.createElement('div');
    el.className='net';
    el.innerHTML='<strong>'+esc(n.ssid)+'</strong><span class="signal '+q[1]+'">'+n.rssi+' dBm</span>'+
      '<span class="meta">'+esc(n.security)+' · canale '+n.channel+'</span><span class="meta">'+q[0]+'</span>';
    el.onclick=()=>selectNetwork(n,el); list.appendChild(el);
  }
  state.textContent=nets.length+' networks detected. Select one to fill in the SSID.';
}
async function poll(){
  try{
    const r=await fetch('/api/wifi/scan',{cache:'no-store'});
    const j=await r.json();
    if(j.state==='scanning'){
      state.textContent='Scanning…';
      timer=setTimeout(poll,500);
    }else{
      btn.disabled=false; render(j.networks||[]);
    }
  }catch(e){
    btn.disabled=false; state.textContent='Scan error: '+e;
  }
}
btn.onclick=()=>{
  btn.disabled=true; list.innerHTML=''; state.textContent='Starting scan…';
  if(timer)clearTimeout(timer); poll();
};
document.getElementById('wifiForm').addEventListener('submit',()=>{
  // Disabled controls are not submitted; open networks must send empty password.
  if(pass.disabled){pass.disabled=false;pass.value=''}
});
</script></main></body></html>
)HTML");
    return page;
}

String HttpServer::buildStatusPage() const
{
    static constexpr char page[] = R"HTML(
<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SwitchNet</title>
<style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;--bg:#0d1015;--panel:#171b22;--panel2:#10141a;--border:#2a303a;--text:#f4f6f8;--muted:#929baa;--ok:#65df9a;--warn:#f4c36a;--accent:#558cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text)}main{max-width:1120px;margin:auto;padding:26px 18px 60px}.top{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:20px}.brand h1{margin:0;font-size:2rem}.brand p{margin:5px 0 0;color:var(--muted)}.badge{padding:7px 11px;border-radius:999px;background:#163323;color:var(--ok);font-weight:700;font-size:.84rem}.columns{display:grid;grid-template-columns:1.4fr .9fr;gap:16px}.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:19px;margin-bottom:16px}.card h2{font-size:1.05rem;margin:0 0 16px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{background:var(--panel2);border-radius:10px;padding:12px;min-height:67px}.label{color:var(--muted);font-size:.77rem}.value{font-weight:700;margin-top:5px;overflow-wrap:anywhere}.controller{display:grid;grid-template-columns:1fr 1fr;gap:14px}.axis{margin:10px 0}.axis-head{display:flex;justify-content:space-between;font-size:.8rem}.track{height:8px;background:#252b34;border-radius:99px;overflow:hidden;margin-top:5px}.fill{height:100%;width:50%;background:var(--accent);transition:width .08s linear}.buttons{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.btnstate{border:1px solid var(--border);border-radius:999px;padding:5px 9px;color:var(--muted);font-size:.77rem}.btnstate.on{background:#214b34;border-color:#3c8b60;color:#b8f4d1}label{display:block;color:var(--muted);font-size:.8rem;margin:13px 0 6px}input,select{width:100%;padding:10px 11px;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:8px;font:inherit}.check{display:flex;align-items:center;gap:9px;margin-top:15px;color:var(--text)}.check input{width:auto;padding:0}.check span{font-size:.9rem}button{margin-top:16px;width:100%;padding:11px;border:0;border-radius:9px;background:var(--accent);color:#fff;font-weight:750;cursor:pointer}.future{margin-top:15px;padding-top:13px;border-top:1px solid var(--border);color:var(--muted);font-size:.8rem}.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.chip{border:1px dashed #414957;border-radius:999px;padding:5px 8px}.notice{font-size:.8rem;color:var(--warn);margin-top:10px}.small{font-size:.78rem;color:var(--muted)}.progress{height:9px;background:#252b34;border-radius:99px;overflow:hidden;margin-top:10px}.progress>div{height:100%;width:0;background:var(--ok);transition:width .12s linear}.danger{background:#2e496f}.ota-row{display:flex;gap:8px;align-items:center}.ota-row input{flex:1}@media(max-width:850px){.columns{grid-template-columns:1fr}.grid{grid-template-columns:1fr 1fr}}@media(max-width:520px){.top{align-items:start;flex-direction:column}.grid,.controller{grid-template-columns:1fr}}
</style>
</head>
<body><main>
<div class="top"><div class="brand"><h1>SwitchNet</h1><p>Network controller bridge</p></div><div class="badge" id="health">ONLINE</div></div>
<div class="columns"><div>
<section class="card"><h2>Status</h2><div class="grid">
<div class="metric"><div class="label">Firmware</div><div class="value" id="version">-</div></div>
<div class="metric"><div class="label">Wi-Fi</div><div class="value" id="wifi">-</div></div>
<div class="metric"><div class="label">IP / RSSI</div><div class="value" id="network">-</div></div>
<div class="metric"><div class="label">Client</div><div class="value" id="client">-</div></div>
<div class="metric"><div class="label">UDP</div><div class="value" id="udp">-</div></div>
<div class="metric"><div class="label">USB</div><div class="value" id="usb">-</div></div>
<div class="metric"><div class="label">Packet loss</div><div class="value" id="loss">-</div></div>
<div class="metric"><div class="label">Wi-Fi recovery</div><div class="value" id="recovery">-</div></div>
<div class="metric"><div class="label">Emulated controller</div><div class="value" id="mode">-</div></div>
</div></section>
<section class="card"><h2>Diagnostics</h2><div class="grid">
<div class="metric"><div class="label">UDP received / lost</div><div class="value" id="udpCounters">-</div></div>
<div class="metric"><div class="label">CRC / out of order</div><div class="value" id="protocolCounters">-</div></div>
<div class="metric"><div class="label">USB report/s</div><div class="value" id="usbRate">-</div></div>
<div class="metric"><div class="label">USB OUT</div><div class="value" id="usbOut">-</div></div>
<div class="metric"><div class="label">Handshake</div><div class="value" id="handshake">-</div></div>
<div class="metric"><div class="label">Report mode</div><div class="value" id="reportMode">-</div></div>
<div class="metric"><div class="label">Rumble TX</div><div class="value" id="rumbleTx">-</div></div>
<div class="metric"><div class="label">Rumble errors</div><div class="value" id="rumbleErrors">-</div></div>
</div></section>
<section class="card"><h2>Controllers</h2>
<div class="small">SwitchNet exposes two independent Nintendo Pro Controller interfaces. P2 activates automatically when a client sends controller slot 2; no ESP32 reboot is required.</div>
<div class="grid" style="margin-top:10px">
<div class="metric"><div class="label">Connected slots</div><div class="value" id="controllerSlots">0 / 2</div></div>
<div class="metric"><div class="label">P1 network</div><div class="value" id="controllerP1">disconnected</div></div>
<div class="metric"><div class="label">P2 network</div><div class="value" id="controllerP2">disconnected</div></div>
<div class="metric"><div class="label">P1 identity</div><div class="value" id="dualLabP1Mac">-</div></div>
<div class="metric"><div class="label">P2 identity</div><div class="value" id="dualLabP2Mac">-</div></div>
<div class="metric"><div class="label">P2 USB</div><div class="value" id="dualLabSecond">closed</div></div>
</div>
</section>
<section class="card"><h2>Switch 2 Wake</h2>
<div class="small">Live Switch 2 BLE wake and one-time Joy-Con 2 identity capture.</div>
<div class="grid" style="margin-top:12px">
<div class="metric"><div class="k">Wake identity</div><div class="v" id="wakeIdentity">Not captured</div></div>
<div class="metric"><div class="k">Last capture RSSI</div><div class="v" id="wakeRssi">-</div></div>
</div>
<div class="grid" style="margin-top:10px">
<div class="metric"><div class="label">Switch USB state</div><div class="value" id="switchUsbState">-</div></div>
<div class="metric"><div class="label">Auto wake</div><div class="value" id="autoWakeState">-</div></div>
<div class="metric"><div class="label">Last reason</div><div class="value" id="autoWakeReason">-</div></div>
</div>
<button type="button" id="wakeButton">Wake Switch 2</button>
<button type="button" id="wakeCaptureButton">Capture Joy-Con 2 Identity</button>
<button type="button" class="danger" id="wakeClearButton">Clear Wake Identity</button>
<div class="small" style="margin-top:12px">Capture: hold HOME on a paired Joy-Con 2. SwitchNet returns automatically.</div>
<div class="notice" id="wakeNotice"></div>
</section>

</div><aside>

<section class="card"><h2>Configuration</h2>
<a href="/network" style="display:block;text-align:center;text-decoration:none;padding:10px;border:1px solid var(--border);border-radius:9px;color:var(--text);margin-bottom:14px">Wi-Fi Network / SSID / password</a>
<form id="configForm">
<label for="controllerMode">Emulated controller</label><select id="controllerMode" name="controller_mode"><option value="switch_pro">Nintendo Switch Pro Controller</option></select>
<label for="hostname">Hostname</label><input id="hostname" name="hostname" maxlength="31" required>
<label for="udpPort">UDP port</label><input id="udpPort" name="udp_port" type="number" min="1024" max="65535" required>
<label class="check"><input id="autoWakeEnabled" type="checkbox"> <span>Auto wake on controller client connect</span></label>
<div class="small">Wake Switch 2 automatically when a controller client connects and USB host activity is not detected.</div>
<label class="check"><input id="rumbleEnabled" name="rumble_enabled" type="checkbox" value="1"> <span>Enable rumble for the source controller</span></label>
<label for="rumbleIntensity">Rumble intensity: <strong id="rumbleIntensityValue">100%</strong></label>
<input id="rumbleIntensity" type="range" min="0" max="100" step="1" value="100" style="width:100%">
<div class="small">Enable state and intensity are applied immediately and do not require a restart.</div>
<div class="notice" id="rumbleNotice"></div>
<button type="submit">Save and restart other settings</button><div class="notice" id="saveNotice"></div></form>

</section>
<section class="card"><h2>OTA firmware update</h2>
<div class="small">Upload the <code>SwitchNet.ino.bin</code> file generated by arduino-cli. Wi-Fi credentials and Preferences are preserved.</div>
<form id="otaForm"><label for="firmwareFile">Firmware .bin</label><input id="firmwareFile" type="file" accept=".bin,application/octet-stream" required><button class="danger" type="submit" id="otaButton">Upload firmware and restart</button></form>
<div class="progress"><div id="otaProgress"></div></div><div class="notice" id="otaNotice"></div>
</section>
<section class="card"><h2>Information</h2><div class="small">Hostname/UDP changes restart SwitchNet. Rumble and auto wake apply live. OTA requires router Wi-Fi.<br><strong>OTA layout:</strong> Dual-slot 1728 KiB.</div></section>
<section class="card"><h2>HTTP API Reference</h2><pre class="small">GET  /                    Dashboard/setup
GET  /network             Wi-Fi settings
GET  /api/status          Runtime state
GET  /api/config          Configuration
GET  /api/routes          API inventory
GET  /api/wifi/scan       Wi-Fi scan
POST /wifi                Save Wi-Fi
POST /api/config          Save config
POST /api/rumble          Rumble
POST /api/auto-wake       Auto wake
POST /api/dual-usb-lab     Deprecated compatibility
POST /api/wake            Wake Switch 2
POST /api/wake/capture    Capture identity
POST /api/wake/clear      Clear identity
POST /api/ota             Firmware OTA</pre></section>
<section class="card"><h2>Network Discovery</h2><div class="small"><code>http://switchnet.local</code> uses SwitchNet's built-in multicast DNS responder with automatic rejoin after Wi-Fi/DHCP changes. Clients also use UDP 5455 discovery, so DHCP changes require no manual IP update.</div></section>
</aside></div>
<script>
const $=id=>document.getElementById(id), set=(id,v)=>$(id).textContent=v;
let configLoaded=false,otaUiActive=false;
async function refresh(){if(otaUiActive)return;try{const r=await fetch('/api/status',{cache:'no-store'});const s=await r.json();set('health','ONLINE');set('version',s.version);set('wifi',s.wifi_connected?s.ssid:s.wifi_mode);set('network',s.wifi_connected?`${s.ip} / ${s.rssi} dBm`:'-');set('client',s.controller_client_connected?`${s.controller_client_ip}:${s.controller_client_port}`:'disconnected');set('udp',`${s.udp_packets_per_second} pps / :${s.udp_port}`);set('usb',s.usb_connected?'Pro Controller enumerated':(s.usb_started?'USB started':'waiting for client'));set('loss',`${s.udp_packets_lost} lost`);set('recovery',`${s.wifi_disconnect_count} drop / ${s.wifi_recovery_restarts} restart`);set('mode',s.emulated_controller_name);set('udpCounters',`${s.udp_packets_received} / ${s.udp_packets_lost}`);set('protocolCounters',`${s.udp_crc_errors} / ${s.udp_out_of_order_packets}`);set('usbRate',s.usb_reports_per_second);set('usbOut',s.usb_output_reports_received);set('handshake',s.usb_handshake_responses_sent);set('reportMode',s.usb_report_mode_30?'0x30 active':'waiting');set('rumbleTx',s.rumble_enabled?s.rumble_packets_sent:'disabled');set('rumbleErrors',s.rumble_send_failures);set('wakeIdentity',s.wake_identity_ready?(s.wake_identity_mac||'Ready'):'Not captured');set('wakeRssi',s.wake_last_capture_rssi?`${s.wake_last_capture_rssi} dBm`:'-');set('switchUsbState',s.switch_usb_state||'unknown');set('controllerSlots',`${s.controller_slots_connected||0} / 2`);set('controllerP1',s.controller_slot_1_connected?`${s.controller_slot_1_ip}:${s.controller_slot_1_port}`:'disconnected');set('controllerP2',s.controller_slot_2_connected?`${s.controller_slot_2_ip}:${s.controller_slot_2_port}`:'disconnected');set('dualLabSecond',s.dual_usb_second_open?'open':'closed');set('dualLabP1Mac',s.dual_usb_primary_identity_mac||'-');set('dualLabP2Mac',s.dual_usb_secondary_identity_mac||'-');set('autoWakeState',s.auto_wake_enabled?(s.auto_wake_pending?'waiting':'enabled'):'disabled');set('autoWakeReason',s.auto_wake_last_reason||'-');$('autoWakeEnabled').checked=!!s.auto_wake_enabled;$('wakeButton').disabled=!s.wake_identity_ready}catch(e){set('health','OFFLINE')}}
async function loadConfig(){try{const r=await fetch('/api/config',{cache:'no-store'});const c=await r.json();$('controllerMode').value=c.controller_mode;$('hostname').value=c.hostname;$('udpPort').value=c.udp_port;$('rumbleEnabled').checked=!!c.rumble_enabled;$('rumbleIntensity').value=c.rumble_intensity??100;$('autoWakeEnabled').checked=!!c.auto_wake_enabled;set('rumbleIntensityValue',`${$('rumbleIntensity').value}%`);configLoaded=true}catch(e){}}

$('autoWakeEnabled').addEventListener('change',async e=>{
  const enabled=e.target.checked;
  set('autoWakeState',enabled?'enabling...':'disabling...');
  const body=new URLSearchParams({enabled:enabled?'true':'false'});
  try{
    const r=await fetch('/api/auto-wake',{
      method:'POST',
      headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body
    });
    const j=await r.json();
    if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
    e.target.checked=!!j.auto_wake_enabled;
    set('autoWakeState',j.auto_wake_enabled?'enabled':'disabled');
  }catch(err){
    e.target.checked=!enabled;
    set('autoWakeState','error');
    set('wakeNotice','Auto wake error: '+err.message);
  }
});

$('wakeButton').addEventListener('click',async()=>{
  $('wakeButton').disabled=true;
  set('wakeNotice','Sending Switch 2 BLE wake beacon...');
  try{
    const r=await fetch('/api/wake',{method:'POST'});
    const j=await r.json();
    if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
    set('wakeNotice','Wake beacon started. SwitchNet remains online.');
  }catch(err){
    $('wakeButton').disabled=false;
    set('wakeNotice','Wake error: '+err.message);
  }
});

$('wakeCaptureButton').addEventListener('click',async()=>{
  if(!confirm('SwitchNet will go offline for up to 60 seconds. Hold HOME on the paired Joy-Con 2 immediately after confirming.'))return;
  $('wakeCaptureButton').disabled=true;
  set('wakeNotice','Scheduling capture. Hold HOME on the Joy-Con 2 now...');
  try{
    const r=await fetch('/api/wake/capture',{method:'POST'});
    const j=await r.json();
    if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
    set('wakeNotice','Capture mode scheduled. SwitchNet is rebooting...');
  }catch(err){
    $('wakeCaptureButton').disabled=false;
    set('wakeNotice','Capture error: '+err.message);
  }
});

$('wakeClearButton').addEventListener('click',async()=>{
  if(!confirm('Clear the saved Joy-Con 2 wake identity?'))return;
  try{
    const r=await fetch('/api/wake/clear',{method:'POST'});
    const j=await r.json();
    if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
    set('wakeIdentity','Not captured');
    set('wakeRssi','-');
    $('wakeButton').disabled=true;
    set('wakeNotice','Wake identity cleared.');
  }catch(err){
    set('wakeNotice','Clear error: '+err.message);
  }
});

let rumbleIntensityTimer=null;
$('rumbleIntensity').addEventListener('input',e=>{
  set('rumbleIntensityValue',`${e.target.value}%`);
  if(!configLoaded)return;
  clearTimeout(rumbleIntensityTimer);
  rumbleIntensityTimer=setTimeout(async()=>{
    const value=e.target.value;
    set('rumbleNotice',`Setting intensity ${value}%...`);
    try{
      const body=new URLSearchParams({intensity:value});
      const r=await fetch('/api/rumble',{
        method:'POST',
        headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body
      });
      const j=await r.json();
      if(!r.ok||!j.ok)throw new Error(j.error||'error');
      set('rumbleIntensityValue',`${j.rumble_intensity}%`);
      $('rumbleIntensity').value=j.rumble_intensity;
      set('rumbleNotice',`Rumble intensity: ${j.rumble_intensity}%`);
    }catch(err){
      set('rumbleNotice','Error: '+err.message);
    }
  },180);
});
$('rumbleEnabled').addEventListener('change',async e=>{
  if(!configLoaded)return;
  const enabled=e.target.checked;
  e.target.disabled=true;
  set('rumbleNotice',enabled?'Enabling rumble...':'Disabling rumble...');
  try{
    const body=new URLSearchParams({enabled:enabled?'1':'0'});
    const r=await fetch('/api/rumble',{
      method:'POST',
      headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body
    });
    const j=await r.json();
    if(!r.ok||!j.ok)throw new Error(j.error||'error');
    set('rumbleNotice',j.rumble_enabled?'Rumble enabled.':'Rumble disabled.');
  }catch(err){
    e.target.checked=!enabled;
    set('rumbleNotice','Error: '+err.message);
  }finally{
    e.target.disabled=false;
  }
});
$('configForm').addEventListener('submit',async e=>{e.preventDefault();set('saveNotice','Saving...');const body=new URLSearchParams(new FormData(e.target));try{const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const j=await r.json();if(!r.ok)throw new Error(j.error||'error');set('saveNotice','Saved. SwitchNet is restarting...')}catch(err){set('saveNotice','Error: '+err.message)}});
$('otaForm').addEventListener('submit',e=>{e.preventDefault();const file=$('firmwareFile').files[0];if(!file){set('otaNotice','Select a .bin file');return}if(!file.name.toLowerCase().endsWith('.bin')){set('otaNotice','The firmware must be a .bin file');return}if(!confirm(`Install ${file.name} (${Math.round(file.size/1024)} KiB)? SwitchNet will restart.`))return;const data=new FormData();data.append('firmware',file,file.name);const xhr=new XMLHttpRequest();otaUiActive=true;$('otaButton').disabled=true;set('otaNotice','Upload firmware...');$('otaProgress').style.width='0%';xhr.upload.onprogress=ev=>{if(ev.lengthComputable)$('otaProgress').style.width=`${Math.round(ev.loaded/ev.total*100)}%`};xhr.onload=()=>{try{const j=JSON.parse(xhr.responseText||'{}');if(xhr.status<200||xhr.status>=300||!j.ok)throw new Error(`${j.error||`HTTP ${xhr.status}`}${j.code!==undefined?` (code ${j.code}, ${j.bytes||0} bytes)`:''}`);$('otaProgress').style.width='100%';set('otaNotice',`Firmware received (${j.bytes} bytes). Restarting...`)}catch(err){otaUiActive=false;$('otaButton').disabled=false;set('otaNotice','OTA error: '+err.message)}};xhr.onerror=()=>{otaUiActive=false;$('otaButton').disabled=false;set('otaNotice','Network error during OTA')};xhr.open('POST','/api/ota');xhr.timeout=120000;xhr.ontimeout=()=>{otaUiActive=false;$('otaButton').disabled=false;set('otaNotice','OTA timeout')};xhr.send(data)});
loadConfig();refresh();setInterval(refresh,2000);
</script></main></body></html>
)HTML";

    return String(page);
}

String HttpServer::buildStatusJson() const
{
    String json;
    json.reserve(2500);

    json += F("{\"service\":\"SwitchNet\"");
    json += F(",\"version\":\"");
    json += jsonEscape(SWITCHNET_VERSION);
    json += '"';

    json += F(",\"ota_in_progress\":");
    json += otaInProgress_ ? F("true") : F("false");
    json += F(",\"ota_last_success\":");
    json += otaSuccess_ ? F("true") : F("false");
    json += F(",\"ota_bytes_written\":");
    json += String(otaBytesWritten_);
    json += F(",\"ota_error_code\":");
    json += String(otaErrorCode_);
    json += F(",\"ota_last_error\":\"");
    json += jsonEscape(otaError_);
    json += '"';
    json += F(",\"ota_free_sketch_space\":");
    json += String(ESP.getFreeSketchSpace());

    json += F(",\"emulated_controller\":\"");
    json += jsonEscape(emulatedControllerId(config_.emulatedController));
    json += '"';
    json += F(",\"emulated_controller_name\":\"");
    json += jsonEscape(emulatedControllerName(config_.emulatedController));
    json += '"';

    json += F(",\"wifi_mode\":\"");
    json += jsonEscape(wifi_.modeName());
    json += '"';
    json += F(",\"wifi_connected\":");
    json += wifi_.connected() ? F("true") : F("false");

    json += F(",\"ssid\":\"");
    if (wifi_.connected()) json += jsonEscape(WiFi.SSID());
    json += '"';

    json += F(",\"ip\":\"");
    if (wifi_.connected()) json += WiFi.localIP().toString();
    else if (wifi_.accessPointActive()) json += WiFi.softAPIP().toString();
    json += '"';

    json += F(",\"rssi\":");
    json += wifi_.connected() ? String(WiFi.RSSI()) : String(0);
    json += F(",\"wifi_ever_connected\":");
    json += wifi_.everConnected() ? F("true") : F("false");
    json += F(",\"wifi_disconnect_count\":");
    json += String(wifi_.disconnectCount());
    json += F(",\"wifi_reconnect_attempts\":");
    json += String(wifi_.reconnectAttempts());
    json += F(",\"wifi_recovery_restarts\":");
    json += String(wifi_.recoveryRestarts());
    json += F(",\"wifi_offline_ms\":");
    json += String(wifi_.offlineDurationMs());
    json += F(",\"wifi_low_latency_mode\":");
    json += wifi_.lowLatencyMode() ? F("true") : F("false");
    json += F(",\"wifi_sta_mac\":\"");
    json += WiFi.macAddress();
    json += '"';
    json += F(",\"mdns_ready\":");
    json += discovery_.mdnsReady() ? F("true") : F("false");
    json += F(",\"mdns_hostname\":\"");
    json += jsonEscape(discovery_.hostname());
    json += F(".local\"");
    json += F(",\"discovery_udp_ready\":");
    json += discovery_.udpReady() ? F("true") : F("false");
    json += F(",\"discovery_udp_port\":5455");
    json += F(",\"discovery_requests\":");
    json += String(discovery_.requests());
    json += F(",\"wake_identity_ready\":");
    json += wake_.identityReady() ? F("true") : F("false");
    json += F(",\"wake_identity_mac\":\"");
    json += jsonEscape(wake_.identityMac());
    json += '"';
    json += F(",\"wake_last_capture_rssi\":");
    json += String(wake_.lastCaptureRssi());
    json += F(",\"auto_wake_enabled\":");
    json += config_.autoWakeEnabled ? F("true") : F("false");
    json += F(",\"auto_wake_pending\":");
    json += autoWake_.pending() ? F("true") : F("false");
    json += F(",\"auto_wake_attempts\":");
    json += String(autoWake_.attempts());
    json += F(",\"auto_wake_successes\":");
    json += String(autoWake_.successes());
    json += F(",\"auto_wake_last_attempt_age_ms\":");
    json += String(autoWake_.lastAttemptAgeMs());
    json += F(",\"auto_wake_last_reason\":\"");
    json += jsonEscape(autoWake_.lastReason());
    json += '"';
    json += F(",\"switch_usb_state\":\"");
    json += jsonEscape(autoWake_.switchUsbState());
    json += '"';
    json += F(",\"switch_host_active\":");
    json += autoWake_.hostActive() ? F("true") : F("false");
    json += F(",\"usb_host_activity_age_ms\":");
    json += String(backend_.lastHostActivityAgeMs());

    json += F(",\"udp_port\":");
    json += String(config_.udpPort);
    json += F(",\"udp_listening\":");
    json += udp_.listening() ? F("true") : F("false");
    json += F(",\"controller_client_connected\":");
    json += udp_.clientConnected() ? F("true") : F("false");
    json += F(",\"controller_slots_connected\":");
    json += String(udp_.connectedControllerCount());
    json += F(",\"controller_slot_1_connected\":");
    json += udp_.slotConnected(0) ? F("true") : F("false");
    json += F(",\"controller_slot_1_ip\":\"");
    json += jsonEscape(udp_.slotClientIp(0));
    json += '"';
    json += F(",\"controller_slot_1_port\":");
    json += String(udp_.slotClientPort(0));
    json += F(",\"controller_slot_2_connected\":");
    json += udp_.slotConnected(1) ? F("true") : F("false");
    json += F(",\"controller_slot_2_ip\":\"");
    json += jsonEscape(udp_.slotClientIp(1));
    json += '"';
    json += F(",\"controller_slot_2_port\":");
    json += String(udp_.slotClientPort(1));
    json += F(",\"controller_client_ip\":\"");
    json += jsonEscape(udp_.clientIp());
    json += '"';
    json += F(",\"controller_client_port\":");
    json += String(udp_.clientPort());
    json += F(",\"udp_packets_per_second\":");
    json += String(udp_.packetsPerSecond());
    json += F(",\"udp_packets_received\":");
    json += String(udp_.packetsReceived());
    json += F(",\"udp_packets_lost\":");
    json += String(udp_.packetsLost());
    json += F(",\"udp_invalid_packets\":");
    json += String(udp_.invalidPackets());
    json += F(",\"udp_foreign_packets\":");
    json += String(udp_.foreignPackets());
    json += F(",\"udp_last_sequence\":");
    json += String(udp_.lastSequence());
    json += F(",\"udp_last_packet_age_ms\":");
    json += String(udp_.lastPacketAgeMs());
    json += F(",\"udp_crc_errors\":");
    json += String(udp_.crcErrors());
    json += F(",\"udp_protocol_errors\":");
    json += String(udp_.protocolErrors());
    json += F(",\"udp_out_of_order_packets\":");
    json += String(udp_.outOfOrderPackets());
    json += F(",\"udp_session_id\":");
    json += String(udp_.sessionId());
    json += F(",\"udp_client_timestamp_us\":");
    json += String(udp_.lastClientTimestampUs());
    json += F(",\"rumble_enabled\":");
    json += config_.rumbleEnabled ? F("true") : F("false");
    json += F(",\"rumble_intensity\":");
    json += String(config_.rumbleIntensity);
    json += F(",\"rumble_packets_sent\":");
    json += String(udp_.rumblePacketsSent());
    json += F(",\"rumble_send_failures\":");
    json += String(udp_.rumbleSendFailures());
    json += F(",\"rumble_last_sequence\":");
    json += String(udp_.lastRumbleSequence());

    json += F(",\"protocol_version\":3");
    json += F(",\"dual_usb_enabled\":");
    json += backend_.dualHidLabEnabled() ? F("true") : F("false");
    json += F(",\"dual_usb_second_open\":");
    json += backend_.dualHidSecondOpen() ? F("true") : F("false");
    json += F(",\"dual_usb_second_reports_sent\":");
    json += String(backend_.dualHidReportsSent());
    json += F(",\"dual_usb_second_outputs_received\":");
    json += String(backend_.dualHidOutputsReceived());
    json += F(",\"dual_usb_primary_identity_mac\":\"");
    json += jsonEscape(backend_.primaryIdentityMac());
    json += '"';
    json += F(",\"dual_usb_secondary_identity_mac\":\"");
    json += jsonEscape(backend_.secondaryIdentityMac());
    json += '"';
    json += F(",\"dual_usb_secondary_report_mode_30\":");
    json += backend_.secondaryReportMode30() ? F("true") : F("false");

    json += F(",\"usb_backend\":\"");
    json += jsonEscape(backend_.name());
    json += F("\"");
    json += F(",\"usb_connected\":");
    json += backend_.connected() ? F("true") : F("false");
    json += F(",\"usb_started\":");
    json += backend_.started() ? F("true") : F("false");
    json += F(",\"usb_source_connected\":");
    json += backend_.sourceConnected() ? F("true") : F("false");

    json += F(",\"usb_reports_per_second\":");
    json += String(backend_.reportsPerSecond());
    json += F(",\"usb_reports_sent\":");
    json += String(backend_.reportsSent());
    json += F(",\"usb_send_failures\":");
    json += String(backend_.sendFailures());

    json += F(",\"usb_output_reports_received\":");
    json += String(backend_.outputReportsReceived());

    json += F(",\"usb_handshake_responses_sent\":");
    json += String(backend_.handshakeResponsesSent());

    json += F(",\"usb_last_output_report_id\":");
    json += String(backend_.lastOutputReportId());

    json += F(",\"usb_last_command\":");
    json += String(backend_.lastCommand());

    json += F(",\"usb_only_mode\":");
    json += backend_.usbOnlyMode() ? F("true") : F("false");
    json += F(",\"usb_report_mode_30\":");
    json += backend_.reportMode30() ? F("true") : F("false");
    json += F(",\"usb_output_80_count\":");
    json += String(backend_.outputReport80Count());
    json += F(",\"usb_output_01_count\":");
    json += String(backend_.outputReport01Count());
    json += F(",\"usb_output_10_count\":");
    json += String(backend_.outputReport10Count());
    json += F(",\"usb_unknown_output_count\":");
    json += String(backend_.unknownOutputReportCount());
    json += F(",\"usb_replies_queued\":");
    json += String(backend_.repliesQueued());
    json += F(",\"usb_replies_dropped\":");
    json += String(backend_.repliesDropped());
    json += F(",\"usb_last_output_length\":");
    json += String(backend_.lastOutputLength());
    json += F(",\"usb_last_output_hex\":\"");
    json += jsonEscape(backend_.lastOutputHex());
    json += '"';
    json += F(",\"usb_last_reply_hex\":\"");
    json += jsonEscape(backend_.lastReplyHex());
    json += '"';
    json += '}';

    return json;
}

String HttpServer::buildConfigJson() const
{
    String json;
    json.reserve(256);
    json += F("{\"hostname\":\"");
    json += jsonEscape(config_.hostname);
    json += F("\",\"udp_port\":");
    json += String(config_.udpPort);
    json += F(",\"controller_mode\":\"");
    json += jsonEscape(emulatedControllerId(config_.emulatedController));
    json += F("\",\"controller_name\":\"");
    json += jsonEscape(emulatedControllerName(config_.emulatedController));
    json += F("\",\"rumble_enabled\":");
    json += config_.rumbleEnabled ? F("true") : F("false");
    json += F(",\"rumble_intensity\":");
    json += String(config_.rumbleIntensity);
    json += F(",\"auto_wake_enabled\":");
    json += config_.autoWakeEnabled ? F("true") : F("false");
    json += F("}");
    return json;
}

String HttpServer::buildApiRoutesJson() const
{
    return F(
        "["
        "{\"method\":\"GET\",\"path\":\"/\"},"
        "{\"method\":\"GET\",\"path\":\"/network\"},"
        "{\"method\":\"GET\",\"path\":\"/api/status\"},"
        "{\"method\":\"GET\",\"path\":\"/api/config\"},"
        "{\"method\":\"GET\",\"path\":\"/api/routes\"},"
        "{\"method\":\"GET\",\"path\":\"/api/wifi/scan\"},"
        "{\"method\":\"POST\",\"path\":\"/wifi\"},"
        "{\"method\":\"POST\",\"path\":\"/api/config\"},"
        "{\"method\":\"POST\",\"path\":\"/api/rumble\"},"
        "{\"method\":\"POST\",\"path\":\"/api/auto-wake\"},"
        "{\"method\":\"POST\",\"path\":\"/api/dual-usb-lab\"},"
        "{\"method\":\"POST\",\"path\":\"/api/wake\"},"
        "{\"method\":\"POST\",\"path\":\"/api/wake/capture\"},"
        "{\"method\":\"POST\",\"path\":\"/api/wake/clear\"},"
        "{\"method\":\"POST\",\"path\":\"/api/ota\"}"
        "]"
    );
}

String HttpServer::htmlEscape(const String& value)
{
    String escaped;

    escaped.reserve(value.length() + 16);

    for (const char character : value)
    {
        switch (character)
        {
            case '&':
                escaped += F("&amp;");
                break;

            case '<':
                escaped += F("&lt;");
                break;

            case '>':
                escaped += F("&gt;");
                break;

            case '"':
                escaped += F("&quot;");
                break;

            case '\'':
                escaped += F("&#39;");
                break;

            default:
                escaped += character;
                break;
        }
    }

    return escaped;
}

String HttpServer::jsonEscape(const String& value)
{
    String escaped;

    escaped.reserve(value.length() + 16);

    for (const char character : value)
    {
        switch (character)
        {
            case '\\':
                escaped += F("\\\\");
                break;

            case '"':
                escaped += F("\\\"");
                break;

            case '\n':
                escaped += F("\\n");
                break;

            case '\r':
                escaped += F("\\r");
                break;

            case '\t':
                escaped += F("\\t");
                break;

            default:
                escaped += character;
                break;
        }
    }

    return escaped;
}
