"""
树莓派综合服务入口
整合 GPIO 控制、ESP32 桥接 HTTP 服务、网络工具三大模块，
提供统一的启动/停止接口与状态查询。

启动方式：
    python -m raspberry_pi.pi_service
或：
    python raspberry_pi/pi_service.py
"""
import os
import sys
import time
import threading
import signal
from http.server import HTTPServer
from typing import Dict, Optional

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from raspberry_pi.pi_gpio import PiGPIO  # noqa: E402
from raspberry_pi.pi_network import PiNetwork  # noqa: E402
from raspberry_pi.pi_bridge import (  # noqa: E402
    ESP32StatusStore,
    CommandQueue,
    ESP32BridgeHandler,
    BRIDGE_HOST,
    BRIDGE_PORT,
)


class PiService:
    """树莓派综合服务，整合 GPIO、桥接、网络工具。

    使用方式：
        service = PiService()
        service.start()        # 启动桥接 HTTP 服务（后台线程）
        ...
        service.stop()         # 停止服务并释放资源
    """

    def __init__(self,
                 bridge_host: str = BRIDGE_HOST,
                 bridge_port: int = BRIDGE_PORT,
                 gpio_pins: Optional[Dict[str, int]] = None,
                 dht_type: str = "DHT11",
                 wifi_iface: Optional[str] = None):
        """初始化综合服务。

        :param bridge_host: 桥接服务监听地址
        :param bridge_port: 桥接服务监听端口
        :param gpio_pins: 自定义 GPIO 引脚映射
        :param dht_type: 温湿度传感器型号
        :param wifi_iface: Wi-Fi 网卡名
        """
        self.bridge_host = bridge_host
        self.bridge_port = bridge_port
        # GPIO 控制器
        self.gpio = PiGPIO(pins=gpio_pins, dht_type=dht_type)
        # 网络工具
        self.network = PiNetwork(wifi_iface=wifi_iface)
        # ESP32 状态存储与命令队列
        self.status_store = ESP32StatusStore()
        self.command_queue = CommandQueue()
        # 桥接 HTTP 服务相关
        self._http_server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._running = False

    # -------------------- 桥接 HTTP 服务 --------------------
    def _start_bridge_server(self) -> None:
        """在后台线程启动 ESP32 桥接 HTTP 服务。"""
        # 将状态存储与命令队列注入 Handler 类（覆盖全局单例引用）
        handler = ESP32BridgeHandler
        # 通过闭包让 Handler 使用本服务实例的 store/queue
        handler.status_store = self.status_store  # type: ignore[attr-defined]
        handler.command_queue = self.command_queue  # type: ignore[attr-defined]

        # 由于 Handler 内部直接引用模块级全局变量，
        # 这里直接替换模块级单例以确保 Handler 使用本服务的实例
        import raspberry_pi.pi_bridge as _bridge_mod
        _bridge_mod.status_store = self.status_store
        _bridge_mod.command_queue = self.command_queue

        self._http_server = HTTPServer((self.bridge_host, self.bridge_port), handler)
        self._http_server.serve_forever()

    def start(self) -> Dict:
        """启动综合服务（桥接 HTTP 服务在后台线程运行）。"""
        if self._running:
            return {"status": "error", "message": "服务已在运行"}
        try:
            self._server_thread = threading.Thread(
                target=self._start_bridge_server, daemon=True)
            self._server_thread.start()
            self._running = True
            time.sleep(0.2)  # 等待服务启动
            return {
                "status": "ok",
                "message": "PiService 已启动",
                "bridge": f"http://{self.bridge_host}:{self.bridge_port}",
                "gpio": self.gpio.get_status(),
            }
        except Exception as e:
            self._running = False
            return {"status": "error", "message": f"启动失败: {e}"}

    def stop(self) -> Dict:
        """停止综合服务并释放所有资源。"""
        try:
            if self._http_server is not None:
                self._http_server.shutdown()
                self._http_server.server_close()
            self.gpio.cleanup()
            self.network.close()
            self._running = False
            return {"status": "ok", "message": "PiService 已停止"}
        except Exception as e:
            return {"status": "error", "message": f"停止失败: {e}"}

    # -------------------- 统一状态查询 --------------------
    def get_status(self) -> Dict:
        """返回综合服务的整体状态。"""
        return {
            "running": self._running,
            "bridge": {
                "host": self.bridge_host,
                "port": self.bridge_port,
            },
            "esp32": self.status_store.get_status(),
            "gpio": self.gpio.get_status(),
            "command_queue": self.command_queue.stats(),
            "network": self.network.get_info(),
        }

    # -------------------- 便捷命令下发 --------------------
    def send_command(self, command: Dict) -> Dict:
        """向 ESP32 下发一条命令（入队）。"""
        return self.command_queue.put(command)

    def send_robot_command(self, action: str, speed: int = 60, angle: int = 90) -> Dict:
        """快捷下发机器人运动命令。"""
        cmd = {"action": action, "speed": speed, "angle": angle}
        return self.command_queue.put(cmd)


def main() -> None:
    """命令行入口：启动综合服务并阻塞等待中断信号。"""
    service = PiService()
    result = service.start()
    if result.get("status") != "ok":
        print(f"[PiService] 启动失败: {result}")
        sys.exit(1)

    print("[PiService] ========================================")
    print(f"[PiService] 综合服务已启动: {result['bridge']}")
    print(f"[PiService] GPIO 模式: {'硬件' if not service.gpio.mock else 'Mock'}")
    print(f"[PiService] DHT 传感器: {service.gpio.dht_type}")
    print(f"[PiService] Wi-Fi 网卡: {service.network._wifi_iface}")
    print("[PiService] 按 Ctrl+C 停止服务")
    print("[PiService] ========================================")

    # 注册信号处理，优雅退出
    stop_event = threading.Event()

    def _handle_signal(signum, frame):
        print(f"\n[PiService] 收到信号 {signum}，正在停止...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # 阻塞等待中断
    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print(service.stop())


if __name__ == "__main__":
    main()
