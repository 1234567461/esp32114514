#ifndef NETWORK_TOOLS_H
#define NETWORK_TOOLS_H

#include <Arduino.h>
#include <WiFi.h>
#include "config.h"

class NetworkTools {
public:
    // 对单个 IP 做 TCP 端口扫描（connect 扫描，不依赖任何外部工具）
    String scanPorts(const String& ip, int startPort, int endPort);

    // 自定义 ICMP echo（ping），纯手动构造 ICMP 包
    bool ping(const String& ip, int timeoutMs = PING_TIMEOUT_MS);

    // 获取网关 IP
    String getGatewayIP();

    // 获取本机子网掩码
    String getSubnetMask();
};

#endif
