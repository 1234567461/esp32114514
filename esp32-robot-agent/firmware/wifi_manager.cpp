#include "wifi_manager.h"

void WifiManager::begin() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        attempts++;
    }
}

bool WifiManager::isConnected() {
    return WiFi.status() == WL_CONNECTED;
}

String WifiManager::getLocalIP() {
    return WiFi.localIP().toString();
}

int WifiManager::getRSSI() {
    return WiFi.RSSI();
}

String WifiManager::scanNetworksJSON() {
    // 被动扫描周围 AP 的信号强度和信道，不做任何破解
    int n = WiFi.scanNetworks(false, true);
    String json = "{\"networks\":[";
    for (int i = 0; i < n; i++) {
        if (i > 0) json += ",";
        json += "{";
        json += "\"ssid\":\"" + WiFi.SSID(i) + "\",";
        json += "\"rssi\":" + String(WiFi.RSSI(i)) + ",";
        json += "\"channel\":" + String(WiFi.channel(i)) + ",";
        json += "\"encryption\":" + String((int)WiFi.encryptionType(i));
        json += "}";
    }
    json += "]}";
    WiFi.scanDelete();
    return json;
}
