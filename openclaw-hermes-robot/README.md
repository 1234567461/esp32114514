# OpenClaw Hermes Robot

ESP32 机器人 + 自定义网络扫描器 + OpenClaw / Hermes AI Agent 桥接系统。

## ⚠️ 法律声明

本项目仅包含合法的网络诊断功能（端口扫描、连通性测试、信号分析），仅限在**授权的自有网络**中使用。不包含任何攻击模块（中间人、密码破解、DoS、Wi-Fi 破解等）。

## 架构

```
ESP32 机器人 (舵机/超声波/LED)
      │ Wi-Fi
      ▼
树莓派 / PC 桥接层
  ├─ Web 控制面板 (:5000)
  ├─ OpenClaw Bridge (:8080)
  └─ Hermes MCP Server (stdio)
      │
      ▼
  自定义网络工具（纯 socket，不依赖 nmap）
  ├─ TCP 端口扫描 + banner grab
  ├─ ICMP Ping / Traceroute
  ├─ Wi-Fi 信号分析
  └─ 子网主机发现
```

## 目录结构

| 目录 | 说明 |
|------|------|
| `firmware/` | ESP32 固件：Wi-Fi、舵机、自定义 ICMP/TCP 扫描 |
| `network_scanner/` | Python 自定义网络工具（纯 socket） |
| `bridge/` | OpenClaw HTTP 桥接 + Hermes MCP Server |
| `raspberry_pi/` | 树莓派 GPIO + 桥接 + 网络工具封装 |
| `web/` | Web 控制面板（Python 后端 + 原生前端） |

## 快速开始

```bash
pip install -r requirements.txt

# Web 面板
cd web && python server.py   # http://localhost:5000

# OpenClaw 桥接
cd bridge && ESP32_HOST=192.168.1.50 python openclaw_bridge.py

# Hermes MCP
cd bridge && ESP32_HOST=192.168.1.50 python hermes_mcp_server.py
```

## MCP 工具列表（Hermes）

`robot_forward`, `robot_backward`, `robot_turn_left`, `robot_turn_right`,
`robot_stop`, `robot_arm`, `robot_get_status`, `scan_ports`, `discover_hosts`,
`ping_host`, `traceroute`, `wifi_signal`

## 技术栈

ESP32: Arduino C/C++ · 网络工具: Python 标准库 socket · AI 桥接: OpenClaw HTTP + MCP JSON-RPC · Web: http.server + 原生 HTML/CSS/JS
