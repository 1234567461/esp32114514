#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <WiFi.h>
#include "config.h"

class WifiManager {
public:
    void begin();
    bool isConnected();
    String getLocalIP();
    int getRSSI();
    // 扫描周围 Wi-Fi 信号（合法的被动扫描）
    String scanNetworksJSON();
};

#endif
