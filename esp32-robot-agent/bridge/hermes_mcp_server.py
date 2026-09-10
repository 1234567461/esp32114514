"""
Hermes Agent Bridge —— MCP Server
将机器人控制和网络工具以 MCP (Model Context Protocol) 工具形式暴露给 Hermes Agent。
Hermes 通过 stdio JSON-RPC 调用这些工具。

实现的 MCP 工具（均为合法功能）:
  - robot_forward       机器人前进
  - robot_backward      机器人后退
  - robot_turn_left     左转
  - robot_turn_right    右转
  - robot_stop          停止
  - robot_arm           机械臂角度
  - robot_get_status    获取机器人状态
  - scan_ports          TCP 端口扫描
  - discover_hosts      子网主机发现
  - ping_host           ping 连通性测试
  - traceroute          路由追踪
  - wifi_signal         Wi-Fi 信号质量
"""
import json
import sys
import os
import requests
from typing import Dict, Any

from network_scanner.scanner import NetworkScanner
from network_scanner.connectivity_monitor import ConnectivityMonitor
from network_scanner.wifi_analyzer import WifiAnalyzer

ESP32_HOST = os.environ.get("ESP32_HOST", "192.168.1.50")
scanner = NetworkScanner(timeout=1.0, max_workers=32)
monitor = ConnectivityMonitor(timeout=2.0)
wifi = WifiAnalyzer(os.environ.get("WIFI_IFACE", "wlan0"))


# ============ MCP 工具定义 ============

TOOLS = [
    {
        "name": "robot_forward",
        "description": "控制 ESP32 机器人前进",
        "inputSchema": {
            "type": "object",
            "properties": {"speed": {"type": "integer", "minimum": 0, "maximum": 100}},
        },
    },
    {
        "name": "robot_backward",
        "description": "控制 ESP32 机器人后退",
        "inputSchema": {
            "type": "object",
            "properties": {"speed": {"type": "integer", "minimum": 0, "maximum": 100}},
        },
    },
    {
        "name": "robot_turn_left",
        "description": "控制 ESP32 机器人左转",
        "inputSchema": {
            "type": "object",
            "properties": {"speed": {"type": "integer", "minimum": 0, "maximum": 100}},
        },
    },
    {
        "name": "robot_turn_right",
        "description": "控制 ESP32 机器人右转",
        "inputSchema": {
            "type": "object",
            "properties": {"speed": {"type": "integer", "minimum": 0, "maximum": 100}},
        },
    },
    {
        "name": "robot_stop",
        "description": "停止机器人所有运动",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "robot_arm",
        "description": "设置机械臂舵机角度 (0-180)",
        "inputSchema": {
            "type": "object",
            "properties": {"angle": {"type": "integer", "minimum": 0, "maximum": 180}},
            "required": ["angle"],
        },
    },
    {
        "name": "robot_get_status",
        "description": "获取机器人当前状态: IP、RSSI、测距、内存",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "scan_ports",
        "description": "对指定 IP 进行 TCP 端口扫描（connect 扫描），返回开放端口和服务",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip": {"type": "string", "description": "目标 IP 地址"},
                "ports": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "要扫描的端口列表",
                },
            },
            "required": ["ip"],
        },
    },
    {
        "name": "discover_hosts",
        "description": "发现指定子网内存活的主机及开放的常用端口（资产盘点）",
        "inputSchema": {
            "type": "object",
            "properties": {"cidr": {"type": "string", "description": "如 192.168.1.0/24"}},
            "required": ["cidr"],
        },
    },
    {
        "name": "ping_host",
        "description": "对目标主机执行 ping 连通性测试，返回延迟和丢包率统计",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "目标主机 IP 或域名"},
                "count": {"type": "integer", "description": "ping 次数", "default": 5},
            },
            "required": ["host"],
        },
    },
    {
        "name": "traceroute",
        "description": "追踪到目标主机的网络路由路径（TTL 递增）",
        "inputSchema": {
            "type": "object",
            "properties": {"host": {"type": "string", "description": "目标主机"}},
            "required": ["host"],
        },
    },
    {
        "name": "wifi_signal",
        "description": "获取当前 Wi-Fi 连接的信号质量: SSID、BSSID、RSSI、噪声",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ============ 工具实现 ============

def _esp32_command(action: str, **kwargs) -> Dict:
    params = {"action": action}
    params.update(kwargs)
    try:
        resp = requests.get(f"http://{ESP32_HOST}/command", params=params, timeout=3)
        return {"status": "ok", "action": action} if resp.ok else {"status": "error"}
    except requests.RequestException:
        return {"status": "error", "message": "ESP32 不可达"}


def handle_tool(name: str, args: Dict[str, Any]) -> Dict:
    if name == "robot_forward":
        return _esp32_command("forward", speed=args.get("speed", 60))
    if name == "robot_backward":
        return _esp32_command("backward", speed=args.get("speed", 60))
    if name == "robot_turn_left":
        return _esp32_command("left", speed=args.get("speed", 60))
    if name == "robot_turn_right":
        return _esp32_command("right", speed=args.get("speed", 60))
    if name == "robot_stop":
        return _esp32_command("stop")
    if name == "robot_arm":
        return _esp32_command("arm", angle=args.get("angle", 90))
    if name == "robot_get_status":
        try:
            resp = requests.get(f"http://{ESP32_HOST}/status", timeout=3)
            return resp.json() if resp.ok else {"status": "error"}
        except requests.RequestException:
            return {"status": "error", "message": "ESP32 不可达"}
    if name == "scan_ports":
        return scanner.scan_host_ports(
            args["ip"], args.get("ports", [22, 80, 443, 3306, 8080])
        )
    if name == "discover_hosts":
        return {"hosts": scanner.discover_network(args["cidr"])}
    if name == "ping_host":
        return monitor.ping_stats(args["host"], count=args.get("count", 5))
    if name == "traceroute":
        return {"hops": monitor.traceroute(args["host"])}
    if name == "wifi_signal":
        return wifi.get_signal_quality()
    return {"error": f"unknown tool: {name}"}


# ============ MCP JSON-RPC 协议处理 ============

def send_response(msg_id, result=None, error=None):
    resp = {"jsonrpc": "2.0", "id": msg_id}
    if result is not None:
        resp["result"] = result
    if error is not None:
        resp["error"] = error
    sys.stdout.write(json.dumps(resp) + "\n")
    sys.stdout.flush()


def send_notification(method, params):
    msg = {"jsonrpc": "2.0", "method": method, "params": params}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        msg_id = req.get("id")
        params = req.get("params", {})

        if method == "initialize":
            send_response(msg_id, result={
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "esp32-robot-mcp", "version": "1.0.0"},
            })
            send_notification("notifications/initialized", {})

        elif method == "tools/list":
            send_response(msg_id, result={"tools": TOOLS})

        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            try:
                result = handle_tool(name, args)
                send_response(msg_id, result={
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                    "isError": False,
                })
            except Exception as e:
                send_response(msg_id, result={
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True,
                })

        elif method == "ping":
            send_response(msg_id, result={})

        else:
            if msg_id is not None:
                send_response(msg_id, error={"code": -32601, "message": "method not found"})


if __name__ == "__main__":
    main()
