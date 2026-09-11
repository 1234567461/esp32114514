"""
OpenClaw Agent Bridge
将 ESP32 机器人 + 自定义网络工具暴露为 OpenClaw 的工具（MCP 风格）。
"""
import json
import os
import requests
from typing import Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler

from network_scanner.scanner import NetworkScanner
from network_scanner.connectivity_monitor import ConnectivityMonitor
from network_scanner.wifi_analyzer import WifiAnalyzer

BRIDGE_HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "8080"))
ESP32_HOST = os.environ.get("ESP32_HOST", "192.168.1.50")

scanner = NetworkScanner(timeout=1.0, max_workers=32)
monitor = ConnectivityMonitor(timeout=2.0)
wifi = WifiAnalyzer(os.environ.get("WIFI_IFACE", "wlan0"))


class OpenClawBridge:
    @staticmethod
    def robot_move(params: Dict[str, Any]) -> Dict:
        action = params.get("action", "stop")
        speed = params.get("speed", 60)
        try:
            resp = requests.get(f"http://{ESP32_HOST}/command",
                                params={"action": action, "speed": speed}, timeout=3)
            return {"status": "ok", "action": action} if resp.ok else {"status": "error"}
        except requests.RequestException:
            return {"status": "error", "message": "ESP32 不可达"}

    @staticmethod
    def robot_arm(params: Dict[str, Any]) -> Dict:
        angle = params.get("angle", 90)
        try:
            requests.get(f"http://{ESP32_HOST}/command",
                         params={"action": "arm", "angle": angle}, timeout=3)
            return {"status": "ok", "angle": angle}
        except requests.RequestException:
            return {"status": "error", "message": "ESP32 不可达"}

    @staticmethod
    def robot_status(_params=None) -> Dict:
        try:
            resp = requests.get(f"http://{ESP32_HOST}/status", timeout=3)
            return resp.json() if resp.ok else {"status": "error"}
        except requests.RequestException:
            return {"status": "error", "message": "ESP32 不可达"}

    @staticmethod
    def network_scan(params: Dict[str, Any]) -> Dict:
        ip = params.get("ip", "")
        ports = params.get("ports", [22, 80, 443, 3306, 8080])
        if not ip:
            return {"status": "error", "message": "缺少 ip 参数"}
        return scanner.scan_host_ports(ip, ports)

    @staticmethod
    def network_discover(params: Dict[str, Any]) -> Dict:
        cidr = params.get("cidr", "192.168.1.0/24")
        return {"hosts": scanner.discover_network(cidr)}

    @staticmethod
    def network_ping(params: Dict[str, Any]) -> Dict:
        host = params.get("host", "8.8.8.8")
        count = params.get("count", 5)
        return monitor.ping_stats(host, count=count)

    @staticmethod
    def network_traceroute(params: Dict[str, Any]) -> Dict:
        host = params.get("host", "8.8.8.8")
        return {"hops": monitor.traceroute(host)}

    @staticmethod
    def wifi_signal(_params=None) -> Dict:
        return wifi.get_signal_quality()


TOOLS = {
    "robot_move": OpenClawBridge.robot_move,
    "robot_arm": OpenClawBridge.robot_arm,
    "robot_status": OpenClawBridge.robot_status,
    "network_scan": OpenClawBridge.network_scan,
    "network_discover": OpenClawBridge.network_discover,
    "network_ping": OpenClawBridge.network_ping,
    "network_traceroute": OpenClawBridge.network_traceroute,
    "wifi_signal": OpenClawBridge.wifi_signal,
}


class BridgeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return
        tool = data.get("tool")
        params = data.get("params", {})
        if tool not in TOOLS:
            self._send(404, {"error": f"未知工具: {tool}"})
            return
        try:
            result = TOOLS[tool](params)
            self._send(200, result)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_GET(self):
        if self.path == "/tools":
            self._send(200, {"tools": list(TOOLS.keys())})
        elif self.path == "/health":
            self._send(200, {"status": "running"})
        else:
            self._send(404, {"error": "not found"})

    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def run_server():
    server = HTTPServer((BRIDGE_HOST, BRIDGE_PORT), BridgeHandler)
    print(f"[OpenClaw Bridge] 监听 {BRIDGE_HOST}:{BRIDGE_PORT}")
    print(f"[OpenClaw Bridge] 已注册工具: {', '.join(TOOLS.keys())}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
