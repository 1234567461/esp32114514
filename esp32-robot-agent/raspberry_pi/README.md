# 树莓派侧模块 (raspberry_pi)

本目录包含运行在树莓派上的中央控制模块，作为 ESP32 机器人与 Web/AI Agent 之间的桥接枢纽。

## 模块说明

| 文件 | 功能 |
|------|------|
| `__init__.py` | 包标识 |
| `pi_gpio.py` | GPIO 控制：LED、蜂鸣器、继电器/电机、DHT 温湿度 |
| `pi_network.py` | 网络工具统一封装（调用 `network_scanner/`） |
| `pi_bridge.py` | ESP32 桥接 HTTP 服务（状态上报 + 命令队列） |
| `pi_service.py` | 综合启动入口，整合 GPIO + 桥接 + 网络 |

## 环境要求

- 树莓派 3B/4B/Zero 2W，运行 Raspberry Pi OS
- Python 3.7+
- 可选依赖（缺省时自动降级为 Mock 模式，不影响运行）：
  - `RPi.GPIO` — GPIO 控制
  - `Adafruit_DHT` 或 `adafruit-circuitpython-dht` — 温湿度传感器

## 安装

```bash
# 进入项目根目录
cd /path/to/esp32-robot-agent

# 安装 GPIO 库（在树莓派上）
pip install RPi.GPIO

# 可选：DHT 温湿度传感器库
pip install Adafruit_DHT

# 本模块核心不依赖 requests / Flask，仅使用标准库
```

> **注意**：在非树莓派环境（如开发笔记本）运行时，`RPi.GPIO` 无法导入，
> `pi_gpio.py` 会自动进入 Mock 模式，所有 GPIO 操作仅记录日志，不操作硬件，
> 便于开发调试。

## 启动

```bash
# 方式一：作为模块运行
python -m raspberry_pi.pi_service

# 方式二：直接运行
python raspberry_pi/pi_service.py
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PI_HOST` | `0.0.0.0` | HTTP 服务监听地址 |
| `PI_PORT` | `8080` | HTTP 服务端口 |
| `WIFI_IFACE` | `wlan0` | Wi-Fi 网卡接口名 |
| `BRIDGE_HOST` | `0.0.0.0` | （仅 pi_bridge 独立运行时） |
| `BRIDGE_PORT` | `8080` | （仅 pi_bridge 独立运行时） |

## HTTP API 一览

### ESP32 桥接

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/esp32/status` | ESP32 上报状态（JSON） |
| GET | `/esp32/status` | 获取 ESP32 最新状态 |
| POST | `/esp32/command` | Web/AI 提交控制命令（入队） |
| GET | `/esp32/command` | ESP32 拉取下一条命令 |
| GET | `/esp32/commands` | 查看当前命令队列 |
| GET | `/health` | 健康检查 |

**示例 — ESP32 上报状态：**
```bash
curl -X POST http://<pi-ip>:8080/esp32/status \
  -H "Content-Type: application/json" \
  -d '{"battery": 85, "distance": 120, "pose": {"x": 1.2, "y": 0.5, "theta": 90}}'
```

**示例 — Web 下发控制命令：**
```bash
curl -X POST http://<pi-ip>:8080/esp32/command \
  -H "Content-Type: application/json" \
  -d '{"action": "forward", "speed": 60}'
```

**示例 — ESP32 轮询拉取命令：**
```bash
curl http://<pi-ip>:8080/esp32/command
```

### GPIO 控制

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/gpio/led` | LED 控制 `{pin, action: on\|off\|blink}` |
| POST | `/gpio/buzzer` | 蜂鸣器 `{pin, action: on\|off\|beep, frequency?}` |
| POST | `/gpio/relay` | 继电器 `{pin, action: on\|off, active_low?}` |
| POST | `/gpio/motor` | 电机 `{in1, in2, pwm_pin, action, speed?}` |
| POST | `/gpio/dht` | 温湿度 `{pin, sensor: DHT11\|DHT22}` |

**示例 — 点亮 LED：**
```bash
curl -X POST http://<pi-ip>:8080/gpio/led \
  -H "Content-Type: application/json" \
  -d '{"pin": 17, "action": "on"}'
```

### 网络工具

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/network/scan` | 端口扫描 `{ip, ports?}` |
| POST | `/network/discover` | 子网发现 `{cidr}` |
| GET | `/network/ping` | ping 统计 `?host=&count=` |
| GET | `/network/traceroute` | 路由追踪 `?host=` |
| GET | `/wifi/signal` | 当前 Wi-Fi 信号质量 |
| GET | `/wifi/scan` | 扫描周围 AP |

**示例 — 端口扫描：**
```bash
curl -X POST http://<pi-ip>:8080/network/scan \
  -H "Content-Type: application/json" \
  -d '{"ip": "192.168.1.50", "ports": [22, 80, 443]}'
```

> ⚠️ **网络扫描仅限授权的自有网络**，所有功能均为资产盘点和连通性检测，
> 不包含任何攻击行为（中间人、密码破解、DoS 等）。

## 架构流程

```
                    ┌──────────────────────────────────────────┐
                    │           树莓派 (raspberry_pi)          │
                    │                                          │
  Web/AI Agent ───► │  pi_service (HTTP :8080)                 │
                    │   ├─ /esp32/*   → 命令队列 + 状态存储    │
                    │   ├─ /gpio/*    → pi_gpio.py (RPi.GPIO)  │
                    │   └─ /network/* → pi_network.py          │
                    │                      │                   │
                    │                      ▼                   │
                    │              network_scanner/            │
                    │              (scanner/monitor/wifi)      │
                    └───────────────┬──────────────────────────┘
                                    │ HTTP 轮询
                                    ▼
                          ┌─────────────────┐
                          │   ESP32 机器人   │
                          │ (上报状态/拉取命令)│
                          └─────────────────┘
```

## 仅运行桥接服务（不含 GPIO/网络）

```bash
python -m raspberry_pi.pi_bridge
```
