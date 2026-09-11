#include "network_tools.h"
#include <lwip/sockets.h>
#include <lwip/inet.h>

String NetworkTools::scanPorts(const String& ip, int startPort, int endPort) {
    String json = "{\"ip\":\"" + ip + "\",\"open_ports\":[";
    bool first = true;
    IPAddress addr;
    if (!addr.fromString(ip)) return json + "]}";

    for (int port = startPort; port <= endPort; port++) {
        int sock = socket(AF_INET, SOCK_STREAM, 0);
        if (sock < 0) continue;

        int flags = fcntl(sock, F_GETFL, 0);
        fcntl(sock, F_SETFL, flags | O_NONBLOCK);

        struct sockaddr_in server;
        server.sin_family = AF_INET;
        server.sin_port = htons(port);
        server.sin_addr.s_addr = inet_addr(ip.c_str());

        int ret = connect(sock, (struct sockaddr*)&server, sizeof(server));
        if (ret != 0) {
            fd_set fdset;
            struct timeval tv;
            FD_ZERO(&fdset);
            FD_SET(sock, &fdset);
            tv.tv_sec = 0;
            tv.tv_usec = SCAN_CONNECT_TIMEOUT_MS * 1000;
            if (select(sock + 1, NULL, &fdset, NULL, &tv) > 0) {
                int so_error = 0;
                socklen_t len = sizeof(so_error);
                getsockopt(sock, SOL_SOCKET, SO_ERROR, &so_error, &len);
                if (so_error == 0) {
                    if (!first) json += ",";
                    json += String(port);
                    first = false;
                }
            }
        }
        close(sock);
    }
    json += "]}";
    return json;
}

bool NetworkTools::ping(const String& ip, int timeoutMs) {
    int sock = socket(AF_INET, SOCK_RAW, IPPROTO_ICMP);
    if (sock < 0) return false;

    struct timeval tv;
    tv.tv_sec = timeoutMs / 1000;
    tv.tv_usec = (timeoutMs % 1000) * 1000;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = 0;
    addr.sin_addr.s_addr = inet_addr(ip.c_str());

    struct {
        uint8_t type;
        uint8_t code;
        uint16_t checksum;
        uint16_t id;
        uint16_t seq;
        char data[32];
    } icmp;
    memset(&icmp, 0, sizeof(icmp));
    icmp.type = 8;
    icmp.code = 0;
    icmp.id = htons(0x1234);
    icmp.seq = htons(1);
    memset(icmp.data, 'A', sizeof(icmp.data));

    uint32_t sum = 0;
    uint16_t* ptr = (uint16_t*)&icmp;
    for (size_t i = 0; i < sizeof(icmp) / 2; i++) {
        sum += ptr[i];
    }
    sum = (sum >> 16) + (sum & 0xFFFF);
    sum += (sum >> 16);
    icmp.checksum = ~sum;

    bool alive = false;
    if (sendto(sock, &icmp, sizeof(icmp), 0, (struct sockaddr*)&addr, sizeof(addr)) > 0) {
        char recvBuf[128];
        struct sockaddr_in from;
        socklen_t fromLen = sizeof(from);
        if (recvfrom(sock, recvBuf, sizeof(recvBuf), 0, (struct sockaddr*)&from, &fromLen) > 0) {
            uint8_t* icmpReply = (uint8_t*)recvBuf + 20;
            if (icmpReply[0] == 0) alive = true;
        }
    }
    close(sock);
    return alive;
}

String NetworkTools::getGatewayIP() {
    return WiFi.gatewayIP().toString();
}

String NetworkTools::getSubnetMask() {
    return WiFi.subnetMask().toString();
}
