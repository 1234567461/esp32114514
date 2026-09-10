#ifndef CONFIG_H
#define CONFIG_H

// ============ 机器人硬件配置 ============
#define SERVO_PIN_LEFT   13
#define SERVO_PIN_RIGHT  14
#define SERVO_PIN_ARM    15
#define LED_PIN          2
#define TRIG_PIN         5
#define ECHO_PIN         18

// ============ Wi-Fi 配置 ============
#define WIFI_SSID        "YOUR_SSID"
#define WIFI_PASSWORD    "YOUR_PASSWORD"

// ============ 服务器配置 ============
#define BRIDGE_HOST      "192.168.1.100"
#define BRIDGE_PORT      8080
#define BRIDGE_PATH      "/esp32/command"

// ============ 网络工具配置 ============
#define PING_TIMEOUT_MS  1000
#define SCAN_PORT_MAX    1024
#define SCAN_CONNECT_TIMEOUT_MS 500

// ============ 舵机参数 ============
#define SERVO_MIN_PULSE  500
#define SERVO_MAX_PULSE  2400
#define SERVO_FREQ       50

#endif // CONFIG_H
