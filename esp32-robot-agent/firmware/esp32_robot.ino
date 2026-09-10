// ============================================================
// ESP32 Robot Agent Firmware
// 集成: Wi-Fi + 舵机控制 + 自定义网络扫描 + 自定义 ping
// 对接: OpenClaw / Hermes Agent Bridge
// 注意: 本固件仅包含合法的网络诊断功能，不包含任何攻击模块
// ============================================================

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"
#include "wifi_manager.h"
#include "robot_control.h"
#include "network_tools.h"

WifiManager   wifiMgr;
RobotControl  robot;
NetworkTools  netTools;

unsigned long lastReport = 0;
const unsigned long REPORT_INTERVAL = 5000;

void reportStatus() {
    // 上报机器人状态到 Bridge（距离、RSSI、IP）
    if (!wifiMgr.isConnected()) return;
    HTTPClient http;
    String url = String("http://") + BRIDGE_HOST + ":" + BRIDGE_PORT + "/esp32/status";
    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;
    doc["ip"] = wifiMgr.getLocalIP();
    doc["rssi"] = wifiMgr.getRSSI();
    doc["distance"] = robot.readDistance();
    doc["free_heap"] = ESP.getFreeHeap();

    String body;
    serializeJson(doc, body);
    http.POST(body);
    http.end();
}

void fetchAndExecuteCommand() {
    // 从 Bridge 拉取命令并执行
    if (!wifiMgr.isConnected()) return;
    HTTPClient http;
    String url = String("http://") + BRIDGE_HOST + ":" + BRIDGE_PORT + BRIDGE_PATH;
    http.begin(url);
    int code = http.GET();
    if (code == 200) {
        String payload = http.getString();
        StaticJsonDocument<256> doc;
        DeserializationError err = deserializeJson(doc, payload);
        if (!err) {
            String action = doc["action"] | "";
            if (action == "forward")      robot.forward(doc["speed"] | 60);
            else if (action == "backward") robot.backward(doc["speed"] | 60);
            else if (action == "left")     robot.turnLeft(doc["speed"] | 60);
            else if (action == "right")    robot.turnRight(doc["speed"] | 60);
            else if (action == "stop")     robot.stop();
            else if (action == "arm")      robot.setArmServo(doc["angle"] | 90);
            else if (action == "led")      robot.setLED(doc["on"] | false);
        }
    }
    http.end();
}

void setup() {
    Serial.begin(115200);
    delay(100);

    robot.begin();
    wifiMgr.begin();

    Serial.println("=== ESP32 Robot Agent Ready ===");
    Serial.print("IP: ");
    Serial.println(wifiMgr.getLocalIP());
}

void loop() {
    fetchAndExecuteCommand();

    if (millis() - lastReport > REPORT_INTERVAL) {
        lastReport = millis();
        reportStatus();
        robot.setLED(!digitalRead(LED_PIN)); // 心跳闪烁
    }

    // 暴露给串口命令行（调试用）
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd == "scan_wifi") {
            Serial.println(wifiMgr.scanNetworksJSON());
        } else if (cmd.startsWith("scan_ports ")) {
            String ip = cmd.substring(11);
            ip.trim();
            Serial.println(netTools.scanPorts(ip, 1, 1024));
        } else if (cmd.startsWith("ping ")) {
            String ip = cmd.substring(5);
            ip.trim();
            Serial.println(netTools.ping(ip) ? "alive" : "timeout");
        } else if (cmd == "status") {
            Serial.printf("IP=%s RSSI=%d Distance=%.1fcm\n",
                wifiMgr.getLocalIP().c_str(), wifiMgr.getRSSI(), robot.readDistance());
        }
    }
}
