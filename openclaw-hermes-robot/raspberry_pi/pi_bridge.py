"""
ESP32 桥接 HTTP 服务
基于标准库 http.server 实现，提供 ESP32 与树莓派之间的状态上报与命令下发通道。
- CommandQueue：线程安全的命令队列，供上层入队、ESP32 拉取
- ESP32StatusStore：状态存储，基于时间戳判断 ESP32 在线/离线
"""
import json
import time
import threading
import queue
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

# 桥接服务监听地址
BRIDGE_HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "8081"))

# ESP32 状态超时判定（秒）：超过该时间未上报则视为离线
STATUS_TIMEOUT = float(os.environ.get("ESP32_STATUS_TIMEOUT", "15"))


class CommandQueue:
    """线程安全的命令队列。

    上层服务（Web/MCP/Bridge）通过 put() 下发命令，
    ESP32 通过 get() 轮询拉取命令并执行。
    """

    def __init__(self, maxsize: int = 100):
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._total_put = 0   # 累计入队计数
        self._total_get = 0   # 累计出队计数

    def put(self, command: Dict[str, Any]) -> Dict:
        """将命令放入队列。

        :param command: 命令 dict，例如 {"action": "forward", "speed": 60}
        :return: 入队结果 dict
        """
        try:
            if not isinstance(command, dict):
                return {"status": "error", "message": "命令必须为 dict 类型"}
            self._queue.put_nowait(command)
            with self._lock:
                self._total_put += 1
            return {"status": "queued", "command": command, "queue_size": self.size()}
        except queue.Full:
            return {"status": "error", "message": "命令队列已满"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """ESP32 拉取下一条命令。

        :param timeout: 等待超时（秒）
        :return: 命令 dict；超时返回 None
        """
        try:
            cmd = self._queue.get(timeout=timeout)
            with self._lock:
                self._total_get += 1
            return cmd
        except queue.Empty:
            return None
        except Exception:
            return None

    def size(self) -> int:
        """返回当前队列长度。"""
        return self._queue.qsize()

    def clear(self) -> Dict:
        """清空队列。"""
        try:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            return {"status": "ok", "message": "队列已清空"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stats(self) -> Dict:
        """返回队列统计信息。"""
        with self._lock:
            return {
                "queue_size": self.size(),
                "total_put": self._total_put,
                "total_get": self._total_get,
            }


class ESP32StatusStore:
    """ESP32 状态存储，线程安全，含超时离线判断。

    ESP32 周期性调用 update() 上报自身状态，
    上层通过 get_status() 获取最新状态及在线判定。
    """

    def __init__(self, timeout: float = STATUS_TIMEOUT):
        self._lock = threading.Lock()
        self._status: Dict[str, Any] = {}
        self._last_update: float = 0.0
        self._timeout = timeout

    def update(self, data: Dict[str, Any]) -> Dict:
        """ESP32 上报最新状态。

        :param data: 状态 dict，例如 {"ip": "...", "rssi": -65, "distance": 30, "free_heap": 12345}
        :return: 接收结果 dict
        """
        try:
            if not isinstance(data, dict):
                return {"status": "error", "message": "状态必须为 dict 类型"}
            with self._lock:
                self._status = dict(data)
                self._last_update = time.time()
            return {"status": "ok", "received": self._status}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_status(self) -> Dict:
        """获取最新状态及在线判定。

        :return: 状态 dict，包含 online 字段标识在线状态
        """
        with self._lock:
            status = dict(self._status)
            last = self._last_update
            online = (time.time() - last) <= self._timeout and bool(status)
        status["online"] = online
        status["last_update"] = last
        if last:
            status["last_update_iso"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(last))
        else:
            status["last_update_iso"] = None
        return status

    def is_online(self) -> bool:
        """判断 ESP32 是否在线。"""
        with self._lock:
            if not self._status or self._last_update <= 0:
                return False
            return (time.time() - self._last_update) <= self._timeout

    def stats(self) -> Dict:
        """返回存储统计。"""
        with self._lock:
            return {
                "online": self.is_online(),
                "last_update": self._last_update,
                "timeout": self._timeout,
                "has_data": bool(self._status),
            }


# 全局单例，供 HTTP Handler 与外部模块共享
status_store = ESP32StatusStore()
command_queue = CommandQueue()


class ESP32BridgeHandler(BaseHTTPRequestHandler):
    """ESP32 桥接 HTTP 请求处理器。

    路由：
      POST /esp32/status  —— ESP32 上报状态
      GET  /esp32/status  —— 获取最新状态（含在线判定）
      POST /esp32/command —— 上层下发命令入队
      GET  /esp32/command —— ESP32 拉取命令
    """

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/esp32/status":
            self._json(200, status_store.get_status())
        elif path == "/esp32/command":
            # ESP32 拉取命令，最多等待 1 秒
            cmd = command_queue.get(timeout=1.0)
            if cmd is None:
                self._json(200, {"command": None})
            else:
                self._json(200, {"command": cmd})
        elif path == "/esp32/queue/stats":
            self._json(200, command_queue.stats())
        elif path == "/health":
            self._json(200, {"status": "running",
                             "esp32_online": status_store.is_online()})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        data = {}
        if body:
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid JSON"})
                return
        if path == "/esp32/status":
            self._json(200, status_store.update(data))
        elif path == "/esp32/command":
            self._json(200, command_queue.put(data))
        elif path == "/esp32/queue/clear":
            self._json(200, command_queue.clear())
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code: int, obj: Any) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        # 静默日志，避免刷屏
        pass


def run_server(host: str = BRIDGE_HOST, port: int = BRIDGE_PORT) -> None:
    """启动 ESP32 桥接 HTTP 服务。"""
    server = HTTPServer((host, port), ESP32BridgeHandler)
    print(f"[ESP32 Bridge] 监听 http://{host}:{port}")
    print("[ESP32 Bridge] 路由:")
    print("  POST /esp32/status   ESP32 上报状态")
    print("  GET  /esp32/status   获取最新状态")
    print("  POST /esp32/command  命令入队")
    print("  GET  /esp32/command  ESP32 拉取命令")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[ESP32 Bridge] 收到中断信号，停止服务")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
