#ifndef NETWORK_TOOLS_H
#define NETWORK_TOOLS_H

#include <Arduino.h>
#include <WiFi.h>
#include "config.h"

class NetworkTools {
public:
    String scanPorts(const String& ip, int startPort, int endPort);
    bool ping(const String& ip, int timeoutMs = PING_TIMEOUT_MS);
    String getGatewayIP();
    String getSubnetMask();
};

#endif
