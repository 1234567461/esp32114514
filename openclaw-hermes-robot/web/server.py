"""
Web 控制面板后端
整合 ESP32 控制、网络扫描、连通性监控、Wi-Fi 分析，提供 REST API。
使用标准库 http.server，不依赖 Flask 等框架。
"""
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network_scanner.scanner import NetworkScanner
from network_scanner.connectivity_monitor import ConnectivityMonitor
from network_scanner.wifi_analyzer import WifiAnalyzer
from raspberry_pi.pi_gpio import PiGPIO
from raspberry_pi.pi_bridge import ESP32StatusStore, CommandQueue

WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT", "5000"))

scanner = NetworkScanner(timeout=1.0, max_workers=32)
monitor = ConnectivityMonitor(timeout=2.0)
wifi = WifiAnalyzer(os.environ.get("WIFI_IFACE", "wlan0"))
gpio = PiGPIO()
status_store = ESP32StatusStore()
cmd_queue = CommandQueue()

WEB_DIR = os.path.dirname(os.path.abspath(__file__))


class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_file("index.html", "text/html")
        elif path == "/style.css":
            self._serve_file("style.css", "text/css")
        elif path == "/app.js":
            self._serve_file("app.js", "application/javascript")
        elif path == "/api/robot/status":
            self._json(status_store.get_status())
        elif path == "/api/robot/command":
            action = params.get("action", ["stop"])[0]
            speed = int(params.get("speed", ["60"])[0])
            angle = int(params.get("angle", ["90"])[0])
            cmd_queue.put({"action": action, "speed": speed, "angle": angle})
            self._json({"status": "queued", "action": action})
        elif path == "/api/network/scan":
            ip = params.get("ip", [""])[0]
            ports_str = params.get("ports", ["22,80,443,3306,8080"])[0]
            ports = [int(p) for p in ports_str.split(",") if p.strip()]
            if not ip:
                self._json({"error": "缺少 ip 参数"}, 400)
                return
            self._json(scanner.scan_host_ports(ip, ports))
        elif path == "/api/network/discover":
            cidr = params.get("cidr", ["192.168.1.0/24"])[0]
            self._json({"hosts": scanner.discover_network(cidr)})
        elif path == "/api/network/ping":
            host = params.get("host", ["8.8.8.8"])[0]
            count = int(params.get("count", ["5"])[0])
            self._json(monitor.ping_stats(host, count=count))
        elif path == "/api/network/traceroute":
            host = params.get("host", ["8.8.8.8"])[0]
            self._json({"hops": monitor.traceroute(host)})
        elif path == "/api/wifi/signal":
            self._json(wifi.get_signal_quality())
        elif path == "/api/gpio/led":
            on = params.get("on", ["0"])[0] == "1"
            gpio.led_on() if on else gpio.led_off()
            self._json({"status": "ok", "led": on})
        elif path == "/api/gpio/dht":
            self._json(gpio.read_dht())
        elif path == "/api/health":
            self._json({"status": "running"})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data = {}
        if body:
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json({"error": "invalid JSON"}, 400)
                return
        if path == "/api/esp32/status":
            status_store.update(data)
            self._json({"status": "ok"})
        elif path == "/api/esp32/command":
            cmd_queue.put(data)
            self._json({"status": "queued"})
        else:
            self._json({"error": "not found"}, 404)

    def _serve_file(self, filename, content_type):
        filepath = os.path.join(WEB_DIR, filename)
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._json({"error": "file not found"}, 404)

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def run():
    server = HTTPServer((WEB_HOST, WEB_PORT), WebHandler)
    print(f"[Web Panel] 控制面板运行于 http://{WEB_HOST}:{WEB_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
