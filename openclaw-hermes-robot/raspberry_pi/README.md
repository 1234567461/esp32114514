# 树莓派侧模块 (raspberry_pi)

本目录包含 OpenClaw-Hermes-Robot 项目中运行在树莓派上的全部模块，负责 GPIO 外设控制、ESP32 桥接通信、网络诊断工具整合。

## 模块清单

| 文件 | 功能 |
|------|------|
| `__init__.py` | 包标识文件 |
| `pi_gpio.py` | GPIO 控制：LED / 蜂鸣器 / 继电器 / 电机 / DHT 温湿度 |
| `pi_bridge.py` | ESP32 桥接 HTTP 服务（标准库 `http.server`） |
| `pi_network.py` | 网络工具封装（端口扫描 / 主机发现 / Ping / Traceroute / Wi-Fi 信号） |
| `pi_service.py` | 综合启动入口，整合 GPIO + 桥接 + 网络工具 |

## 环境要求

- 树莓派硬件（或 PC 开发环境，自动 Mock 降级）
- Python 3.8+
- （可选）`RPi.GPIO` —— 仅在真实树莓派上需要
- （可选）`Adafruit_DHT` —— 仅在使用 DHT11/DHT22 传感器时需要
- **不依赖** nmap / aircrack / iw / iwlist 等外部网络工具

### 安装依赖（真实树莓派）

```bash
sudo apt-get update
sudo apt-get install -y python3-rpi.gpio
pip3 install Adafruit_DHT
```

在非树莓派环境（如开发机）中，所有 GPIO 相关功能会自动降级为 Mock 模式，方法照常返回 dict，不抛出异常。

## 快速启动

### 1. 综合服务（推荐）

启动后整合 GPIO、ESP32 桥接、网络工具：

```bash
cd /path/to/openclaw-hermes-robot
python3 -m raspberry_pi.pi_service
```

环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BRIDGE_HOST` | `0.0.0.0` | 桥接服务监听地址 |
| `BRIDGE_PORT` | `8081` | 桥接服务监听端口 |
| `WIFI_IFACE` | `wlan0` | Wi-Fi 网卡名 |
| `ESP32_STATUS_TIMEOUT` | `15` | ESP32 状态超时判定（秒） |

### 2. 仅启动 ESP32 桥接服务

```bash
python3 -m raspberry_pi.pi_bridge
```

## ESP32 桥接 HTTP API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/esp32/status` | ESP32 上报状态（JSON body） |
| `GET` | `/esp32/status` | 获取最新状态（含 `online` 字段） |
| `POST` | `/esp32/command` | 命令入队（JSON body） |
| `GET` | `/esp32/command` | ESP32 拉取命令（长轮询 1 秒） |

### 示例

ESP32 上报状态：

```bash
curl -X POST http://<pi-ip>:8081/esp32/status \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.1.50","rssi":-65,"distance":30,"free_heap":12345}'
```

上层下发命令：

```bash
curl -X POST http://<pi-ip>:8081/esp32/command \
  -H "Content-Type: application/json" \
  -d '{"action":"forward","speed":60}'
```

## GPIO 引脚映射（默认 BCM 编号）

| 外设 | 引脚 |
|------|------|
| LED | GPIO 17 |
| 蜂鸣器 | GPIO 18 |
| 继电器 | GPIO 22 |
| 电机 IN1 | GPIO 23 |
| 电机 IN2 | GPIO 24 |
| 电机 PWM | GPIO 25 |
| DHT 数据 | GPIO 4 |

可在实例化 `PiGPIO` 时通过 `pins` 参数自定义：

```python
from raspberry_pi.pi_gpio import PiGPIO

gpio = PiGPIO(pins={"led": 27, "motor_pwm": 12}, dht_type="DHT22")
print(gpio.led_on())
print(gpio.read_dht())
gpio.cleanup()
```

## 网络工具使用

全部基于纯 Python socket 实现，仅用于自有网络的资产盘点与连通性诊断：

```python
from raspberry_pi.pi_network import PiNetwork

net = PiNetwork(timeout=1.0, max_workers=32, wifi_iface="wlan0")

print(net.scan_ports("192.168.1.1", [22, 80, 443]))
print(net.discover_network("192.168.1.0/24"))
print(net.ping("8.8.8.8", count=5))
print(net.traceroute("8.8.8.8"))
print(net.wifi_signal())

net.close()
```

## 作为 systemd 服务（可选）

创建 `/etc/systemd/system/pi-service.service`：

```ini
[Unit]
Description=OpenClaw Hermes Pi Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/path/to/openclaw-hermes-robot
ExecStart=/usr/bin/python3 -m raspberry_pi.pi_service
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pi-service
sudo systemctl status pi-service
```

## 注意事项

- 所有 GPIO 方法均返回 `dict`，即使硬件不可用也只返回带 `mock` 或 `error` 标记的结果，**不会抛出异常**。
- 网络工具（端口扫描、主机发现）仅限在**自有授权网络**内使用，严禁用于未授权目标。
- 若需以非 root 用户运行 ping/traceroute，ICMP 原始套接字可能无权限，模块会自动降级为 TCP ping（traceroute 需 root 权限）。
- LED 闪烁与蜂鸣器音调在后台线程执行，不阻塞主线程。
