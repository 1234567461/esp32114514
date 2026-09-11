"""
Hermes Agent Bridge —— MCP Server
将机器人控制和网络工具以 MCP 工具形式暴露给 Hermes Agent。
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

TOOLS = [
    {"name": "robot_forward", "description": "控制 ESP32 机器人前进",
     "inputSchema": {"type": "object", "properties": {"speed": {"type": "integer", "minimum": 0, "maximum": 100}}}},
    {"name": "robot_backward", "description": "控制 ESP32 机器人后退",
     "inputSchema": {"type": "object", "properties": {"speed": {"type": "integer", "minimum": 0, "maximum": 100}}}},
    {"name": "robot_turn_left", "description": "控制 ESP32 机器人左转",
     "inputSchema": {"type": "object", "properties": {"speed": {"type": "integer", "minimum": 0, "maximum": 100}}}},
    {"name": "robot_turn_right", "description": "控制 ESP32 机器人右转",
     "inputSchema": {"type": "object", "properties": {"speed": {"type": "integer", "minimum": 0, "maximum": 100}}}},
    {"name": "robot_stop", "description": "停止机器人所有运动",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "robot_arm", "description": "设置机械臂舵机角度 (0-180)",
     "inputSchema": {"type": "object", "properties": {"angle": {"type": "integer", "minimum": 0, "maximum": 180}}, "required": ["angle"]}},
    {"name": "robot_get_status", "description": "获取机器人当前状态",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "scan_ports", "description": "对指定 IP 进行 TCP 端口扫描",
     "inputSchema": {"type": "object", "properties": {"ip": {"type": "string"}, "ports": {"type": "array", "items": {"type": "integer"}}}, "required": ["ip"]}},
    {"name": "discover_hosts", "description": "发现指定子网内存活的主机及开放端口",
     "inputSchema": {"type": "object", "properties": {"cidr": {"type": "string"}}, "required": ["cidr"]}},
    {"name": "ping_host", "description": "对目标主机执行 ping 连通性测试",
     "inputSchema": {"type": "object", "properties": {"host": {"type": "string"}, "count": {"type": "integer", "default": 5}}, "required": ["host"]}},
    {"name": "traceroute", "description": "追踪到目标主机的网络路由路径",
     "inputSchema": {"type": "object", "properties": {"host": {"type": "string"}}, "required": ["host"]}},
    {"name": "wifi_signal", "description": "获取当前 Wi-Fi 连接的信号质量",
     "inputSchema": {"type": "object", "properties": {}}},
]


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
        return scanner.scan_host_ports(args["ip"], args.get("ports", [22, 80, 443, 3306, 8080]))
    if name == "discover_hosts":
        return {"hosts": scanner.discover_network(args["cidr"])}
    if name == "ping_host":
        return monitor.ping_stats(args["host"], count=args.get("count", 5))
    if name == "traceroute":
        return {"hops": monitor.traceroute(args["host"])}
    if name == "wifi_signal":
        return wifi.get_signal_quality()
    return {"error": f"unknown tool: {name}"}


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
                "serverInfo": {"name": "openclaw-hermes-robot-mcp", "version": "1.0.0"},
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
