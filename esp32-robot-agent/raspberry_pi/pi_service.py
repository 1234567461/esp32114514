"""
树莓派服务启动入口
=================
整合 GPIO 控制 + ESP32 桥接 + 网络工具，启动统一的 HTTP 服务。

启动后提供以下能力:
  - ESP32 状态上报 / 命令下发（/esp32/*）
  - GPIO 控制：LED、蜂鸣器、继电器、电机、DHT 温湿度（/gpio/*）
  - 网络工具：端口扫描、子网发现、ping、traceroute、Wi-Fi 分析（/network/*, /wifi/*）

运行方式:
  python -m raspberry_pi.pi_service
  或
  python raspberry_pi/pi_service.py
"""
import os
import sys
import json
import logging
from http.server import HTTPServer

# 确保项目根目录在 sys.path 中，便于导入 network_scanner
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from raspberry_pi.pi_gpio import PiGPIO
from raspberry_pi.pi_network import PiNetwork
from raspberry_pi.pi_bridge import BridgeHandler, command_queue, status_store

logger = logging.getLogger("pi_service")

# 全局服务实例（HTTP Handler 通过类属性访问）
_gpio: PiGPIO = None
_network: PiNetwork = None


class ServiceHandler(BridgeHandler):
    """
    扩展 BridgeHandler，增加 GPIO 和网络工具的 HTTP 端点。
    通过类属性 _gpio / _network 注入实例。
    """

    _gpio: PiGPIO = None
    _network: PiNetwork = None

    # ---------- GET ----------
    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        # ---- GPIO 查询类 ----
        if path == "/gpio/state":
            pin = int(self._query_param("pin", "0"))
            state = self._gpio.get_pin_state(pin) if self._gpio else False
            self._send_json(200, {"status": "ok", "pin": pin, "state": state})
            return

        # ---- 网络工具 ----
        if path == "/network/ping":
            host = self._query_param("host", "8.8.8.8")
            count = int(self._query_param("count", "5"))
            result = self._network.ping(host, count=count) if self._network else {"status": "error", "message": "网络模块未初始化"}
            self._send_json(200, result)
            return

        if path == "/network/traceroute":
            host = self._query_param("host", "8.8.8.8")
            result = self._network.traceroute(host) if self._network else {"status": "error"}
            self._send_json(200, result)
            return

        if path == "/wifi/signal":
            result = self._network.wifi_signal() if self._network else {"status": "error"}
            self._send_json(200, result)
            return

        if path == "/wifi/scan":
            result = self._network.wifi_scan() if self._network else {"status": "error"}
            self._send_json(200, result)
            return

        # 其余交给父类（ESP32 相关端点）
        super().do_GET()

    # ---------- POST ----------
    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        data = self._read_json()
        if data is None:
            self._send_json(400, {"error": "invalid JSON"})
            return

        # ---- GPIO 控制 ----
        if path == "/gpio/led":
            # {pin, action: on|off|blink, times?, interval?}
            pin = data.get("pin")
            action = data.get("action", "off")
            if pin is None:
                self._send_json(400, {"error": "缺少 pin 字段"})
                return
            if action == "on":
                r = self._gpio.led_on(pin)
            elif action == "off":
                r = self._gpio.led_off(pin)
            elif action == "blink":
                r = self._gpio.led_blink(pin, times=data.get("times", 3),
                                         interval=data.get("interval", 0.3))
            else:
                self._send_json(400, {"error": "未知 action"})
                return
            self._send_json(200, r)
            return

        if path == "/gpio/buzzer":
            pin = data.get("pin")
            action = data.get("action", "off")
            if pin is None:
                self._send_json(400, {"error": "缺少 pin 字段"})
                return
            if action == "on":
                r = self._gpio.buzzer_on(pin, duration=data.get("duration"))
            elif action == "beep":
                r = self._gpio.buzzer_beep(pin, frequency=data.get("frequency", 1000),
                                           duration=data.get("duration", 0.2))
            else:
                r = self._gpio.buzzer_off(pin)
            self._send_json(200, r)
            return

        if path == "/gpio/relay":
            pin = data.get("pin")
            action = data.get("action", "off")
            active_low = data.get("active_low", True)
            if pin is None:
                self._send_json(400, {"error": "缺少 pin 字段"})
                return
            if action == "on":
                r = self._gpio.relay_on(pin, active_low=active_low)
            else:
                r = self._gpio.relay_off(pin, active_low=active_low)
            self._send_json(200, r)
            return

        if path == "/gpio/motor":
            in1 = data.get("in1")
            in2 = data.get("in2")
            pwm = data.get("pwm_pin")
            action = data.get("action", "stop")
            if None in (in1, in2, pwm):
                self._send_json(400, {"error": "缺少 in1/in2/pwm_pin 字段"})
                return
            if action == "forward":
                r = self._gpio.motor_forward(in1, in2, pwm, speed=data.get("speed", 60))
            elif action == "backward":
                r = self._gpio.motor_backward(in1, in2, pwm, speed=data.get("speed", 60))
            else:
                r = self._gpio.motor_stop(in1, in2, pwm)
            self._send_json(200, r)
            return

        if path == "/gpio/dht":
            pin = data.get("pin", 4)
            sensor_type = data.get("sensor", "DHT22")
            r = self._gpio.read_dht(pin, sensor_type=sensor_type)
            self._send_json(200, r)
            return

        # ---- 网络工具 ----
        if path == "/network/scan":
            ip = data.get("ip")
            ports = data.get("ports")
            if not ip:
                self._send_json(400, {"error": "缺少 ip 字段"})
                return
            r = self._network.scan_ports(ip, ports=ports)
            self._send_json(200, r)
            return

        if path == "/network/discover":
            cidr = data.get("cidr", "192.168.1.0/24")
            r = self._network.discover_network(cidr)
            self._send_json(200, r)
            return

        # 其余交给父类（ESP32 相关端点）
        super().do_POST()

    # ---------- 辅助方法 ----------
    def _query_param(self, name: str, default: str = "") -> str:
        """从 URL 查询字符串中提取参数"""
        if "?" not in self.path:
            return default
        qs = self.path.split("?", 1)[1]
        for pair in qs.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                if k == name:
                    from urllib.parse import unquote
                    return unquote(v)
        return default


class PiService:
    """树莓派综合服务"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 wifi_iface: str = "wlan0"):
        self.host = host
        self.port = port
        self.wifi_iface = wifi_iface
        self._server = None

    def start(self) -> None:
        """初始化所有模块并启动 HTTP 服务"""
        global _gpio, _network

        # 1. 初始化 GPIO
        logger.info("初始化 GPIO 模块...")
        _gpio = PiGPIO(mode="BCM")
        ServiceHandler._gpio = _gpio
        logger.info("GPIO 可用: %s", _gpio.available)

        # 2. 初始化网络工具
        logger.info("初始化网络工具模块...")
        _network = PiNetwork(wifi_iface=self.wifi_iface)
        ServiceHandler._network = _network

        # 3. 启动 HTTP 服务
        logger.info("启动 HTTP 服务: http://%s:%d", self.host, self.port)
        self._server = HTTPServer((self.host, self.port), ServiceHandler)
        logger.info("服务就绪，端点包括:")
        logger.info("  ESP32:  POST/GET /esp32/status, POST/GET /esp32/command")
        logger.info("  GPIO:   POST /gpio/led, /gpio/buzzer, /gpio/relay, /gpio/motor, /gpio/dht")
        logger.info("  网络:   POST /network/scan, /network/discover; GET /network/ping, /network/traceroute")
        logger.info("  Wi-Fi:  GET /wifi/signal, /wifi/scan")

        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """优雅关闭：停止服务并释放资源"""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if _gpio:
            _gpio.cleanup()
        if _network:
            _network.cleanup()
        logger.info("服务已关闭")


def main():
    host = os.environ.get("PI_HOST", "0.0.0.0")
    port = int(os.environ.get("PI_PORT", "8080"))
    wifi_iface = os.environ.get("WIFI_IFACE", "wlan0")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    service = PiService(host=host, port=port, wifi_iface=wifi_iface)
    service.start()


if __name__ == "__main__":
    main()
