#ifndef CONFIG_H
#define CONFIG_H

#define SERVO_PIN_LEFT   13
#define SERVO_PIN_RIGHT  14
#define SERVO_PIN_ARM    15
#define LED_PIN          2
#define TRIG_PIN         5
#define ECHO_PIN         18

#define WIFI_SSID        "YOUR_SSID"
#define WIFI_PASSWORD    "YOUR_PASSWORD"

#define BRIDGE_HOST      "192.168.1.100"
#define BRIDGE_PORT      8080
#define BRIDGE_PATH      "/esp32/command"

#define PING_TIMEOUT_MS  1000
#define SCAN_PORT_MAX    1024
#define SCAN_CONNECT_TIMEOUT_MS 500

#define SERVO_MIN_PULSE  500
#define SERVO_MAX_PULSE  2400
#define SERVO_FREQ       50

#endif
