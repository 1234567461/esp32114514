# ESP32 Robot Agent

ESP32 机器人 + 自定义网络扫描器 + OpenClaw/Hermes AI Agent 桥接系统。

> ⚠️ **法律声明**：本项目仅包含合法的网络诊断功能（端口扫描、连通性测试、信号分析），
> 仅限在**授权的自有网络**中使用。不包含任何攻击模块（中间人、密码破解、DoS、Wi-Fi 破解等）。

## 架构

```
┌──────────────┐     Wi-Fi      ┌──────────────────────────┐
│  ESP32 机器人 │◄──────────────►│  树莓派 / PC 桥接服务器    │
│  (舵机/超声波) │                │                          │
└──────────────┘                │  ┌────────────────────┐  │
                                │  │  OpenClaw Bridge   │  │
┌──────────────┐   HTTP/MCP     │  │  Hermes MCP Server │  │
│  AI Agent    │◄──────────────►│  │  Web Panel (5000)  │  │
│  (OpenClaw/  │                │  └─────────┬──────────┘  │
│   Hermes)    │                │            │             │
└──────────────┘                │  ┌─────────▼──────────┐  │
                                │  │  自定义网络工具       │  │
                                │  │  ├ TCP 端口扫描      │  │
                                │  │  ├ ICMP Ping/Traceroute│
                                │  │  ├ Wi-Fi 信号分析     │  │
                                │  │  └ 子网主机发现       │  │
                                │  └────────────────────┘  │
                                └──────────────────────────┘
```

## 目录结构

| 目录 | 说明 |
|------|------|
| `firmware/` | ESP32 固件（Arduino）：Wi-Fi、舵机、自定义 ICMP/TCP 扫描 |
| `network_scanner/` | Python 自定义网络工具（纯 socket，不依赖 nmap） |
| `bridge/` | OpenClaw HTTP 桥接 + Hermes MCP Server |
| `raspberry_pi/` | 树莓派 GPIO 控制 + 桥接服务 + 网络工具封装 |
| `web/` | Web 控制面板（HTML/CSS/JS + Python 后端） |

## 网络工具（全部自行实现，不依赖外部工具）

| 工具 | 实现方式 | 文件 |
|------|---------|------|
| TCP 端口扫描 | 原始 socket connect + 非阻塞 select | `network_scanner/scanner.py` / `firmware/network_tools.cpp` |
| ICMP Ping | 手动构造 ICMP 报文 + 校验和 | `network_scanner/connectivity_monitor.py` |
| Traceroute | TTL 递增 + ICMP time-exceeded | `network_scanner/connectivity_monitor.py` |
| 子网主机发现 | ICMP 存活探测 + 常用端口扫描 | `network_scanner/scanner.py` |
| Wi-Fi 信号分析 | Linux wireless extensions ioctl | `network_scanner/wifi_analyzer.py` |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 Web 控制面板

```bash
cd web
python server.py
# 访问 http://localhost:5000
```

### 3. 启动 OpenClaw 桥接

```bash
cd bridge
ESP32_HOST=192.168.1.50 python openclaw_bridge.py
```

### 4. 启动 Hermes MCP Server

```bash
cd bridge
ESP32_HOST=192.168.1.50 python hermes_mcp_server.py
```

### 5. 烧录 ESP32 固件

使用 Arduino IDE 或 arduino-cli 编译 `firmware/esp32_robot.ino`，
需要安装库：`ESP32Servo`、`ArduinoJson`。

修改 `firmware/config.h` 中的 Wi-Fi 和服务器地址。

### 6. 树莓派部署

详见 `raspberry_pi/README.md`。

## MCP 工具列表（Hermes）

`robot_forward`, `robot_backward`, `robot_turn_left`, `robot_turn_right`,
`robot_stop`, `robot_arm`, `robot_get_status`, `scan_ports`, `discover_hosts`,
`ping_host`, `traceroute`, `wifi_signal`
