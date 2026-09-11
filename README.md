# OpenClaw Hermes Robot

> ESP32 机器人 + 自定义网络扫描器 + OpenClaw / Hermes AI Agent 桥接系统

把物理机器人、网络诊断工具和 AI Agent 串起来的完整项目。ESP32 负责机器人本体和基础网络扫描，树莓派/PC 负责高级网络工具和 AI Agent 桥接，OpenClaw 与 Hermes 通过 MCP 协议控制机器人并调用网络工具。

项目代码位于 [`openclaw-hermes-robot/`](openclaw-hermes-robot/) 目录。

## ⚠️ 法律与使用边界

本项目**仅包含合法的网络诊断功能**，仅限在**授权的自有网络**中使用：

- ✅ TCP 端口扫描（资产盘点）
- ✅ ICMP Ping / Traceroute（连通性诊断）
- ✅ Wi-Fi 信号强度分析（网络优化）
- ✅ 子网存活主机发现（自有网络资产管理）

**不包含**且**拒绝添加**：中间人攻击、密码暴力破解、网络拒绝服务、Wi-Fi 密码破解、ARP 欺骗、DNS 劫持。

## 快速开始

```bash
cd openclaw-hermes-robot
pip install -r requirements.txt

# Web 控制面板
cd web && python server.py        # http://localhost:5000

# OpenClaw 桥接
cd ../bridge && ESP32_HOST=192.168.1.50 python openclaw_bridge.py

# Hermes MCP Server
ESP32_HOST=192.168.1.50 python hermes_mcp_server.py
```

## 目录

| 目录 | 说明 |
|------|------|
| `openclaw-hermes-robot/firmware/` | ESP32 固件：Wi-Fi、舵机、自定义 ICMP/TCP 扫描 |
| `openclaw-hermes-robot/network_scanner/` | Python 自定义网络工具（纯 socket，不依赖 nmap） |
| `openclaw-hermes-robot/bridge/` | OpenClaw HTTP 桥接 + Hermes MCP Server |
| `openclaw-hermes-robot/raspberry_pi/` | 树莓派 GPIO + 桥接 + 网络工具封装 |
| `openclaw-hermes-robot/web/` | Web 控制面板 |

## MCP 工具（Hermes）

`robot_forward`, `robot_backward`, `robot_turn_left`, `robot_turn_right`,
`robot_stop`, `robot_arm`, `robot_get_status`, `scan_ports`, `discover_hosts`,
`ping_host`, `traceroute`, `wifi_signal`

详见 [openclaw-hermes-robot/README.md](openclaw-hermes-robot/README.md)。
