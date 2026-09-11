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
    String scanNetworksJSON();
};

#endif
