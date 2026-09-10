"""
树莓派中央桥接服务器
===================
使用 Python 标准库 http.server 实现，无额外依赖。

核心职责:
  1. 接收 ESP32 的状态上报  -> POST /esp32/status
  2. 向 ESP32 下发控制命令  -> 命令队列 + GET /esp32/command（ESP32 轮询拉取）
  3. 提供 REST API 供 Web 前端和 AI Agent 调用

端点说明:
  POST /esp32/status        ESP32 上报自身状态（机器人姿态、传感器等）
  GET  /esp32/status        Web/AI 获取 ESP32 最新状态
  POST /esp32/command       Web/AI 提交控制命令（入队）
  GET  /esp32/command       ESP32 拉取下一条待执行命令（出队）
  GET  /esp32/commands      Web/AI 查看当前命令队列
  GET  /health              健康检查
  GET  /api/tools           列出可用工具（供 AI Agent 发现）
"""
import json
import os
import time
import logging
import threading
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional, Deque, Any

logger = logging.getLogger("pi_bridge")


class CommandQueue:
    """线程安全的命令队列，供 Web/AI 入队、ESP32 出队"""

    def __init__(self, maxsize: int = 100):
        self._queue: Deque[Dict[str, Any]] = deque(maxlen=maxsize)
        self._lock = threading.Lock()
        self._seq = 0  # 命令自增序号

    def put(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """入队一条命令，返回带序号的命令对象"""
        with self._lock:
            self._seq += 1
            item = {
                "id": self._seq,
                "timestamp": time.time(),
                **command,
            }
            self._queue.append(item)
            logger.info("命令入队 #%d: %s", self._seq, command.get("action"))
            return item

    def get(self) -> Optional[Dict[str, Any]]:
        """出队下一条命令，无命令时返回 None"""
        with self._lock:
            if not self._queue:
                return None
            item = self._queue.popleft()
            logger.info("命令出队 #%d: %s", item["id"], item.get("action"))
            return item

    def peek_all(self) -> list:
        """查看当前队列中所有命令（不消费）"""
        with self._lock:
            return list(self._queue)

    def size(self) -> int:
        with self._lock:
            return len(self._queue)


class ESP32StatusStore:
    """ESP32 最新状态存储（单条覆盖）"""

    def __init__(self):
        self._status: Dict[str, Any] = {
            "online": False,
            "last_update": 0,
            "battery": 0,
            "distance": 0,
            "pose": {"x": 0, "y": 0, "theta": 0},
        }
        self._lock = threading.Lock()

    def update(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """更新 ESP32 状态"""
        with self._lock:
            self._status.update(status)
            self._status["last_update"] = time.time()
            self._status["online"] = True
            return dict(self._status)

    def get(self) -> Dict[str, Any]:
        """获取最新状态，并根据超时判断是否在线"""
        with self._lock:
            status = dict(self._status)
        # 超过 30 秒未上报视为离线
        if status.get("last_update", 0) and (time.time() - status["last_update"] > 30):
            status["online"] = False
        return status


# 全局单例（HTTP Handler 中使用）
command_queue = CommandQueue()
status_store = ESP32StatusStore()


class BridgeHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    # ---------- 工具方法 ----------
    def _send_json(self, code: int, obj: Any) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> Optional[Dict[str, Any]]:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def do_OPTIONS(self) -> None:
        """CORS 预检请求"""
        self._send_json(204, {})

    # ---------- GET ----------
    def do_GET(self) -> None:
        path = self.path.split("?")[0]  # 去掉查询参数

        if path == "/health":
            self._send_json(200, {"status": "running", "queue_size": command_queue.size()})

        elif path == "/esp32/status":
            # Web/AI 获取 ESP32 最新状态
            self._send_json(200, status_store.get())

        elif path == "/esp32/command":
            # ESP32 轮询拉取下一条命令
            cmd = command_queue.get()
            if cmd:
                self._send_json(200, {"status": "ok", "command": cmd})
            else:
                self._send_json(200, {"status": "ok", "command": None})

        elif path == "/esp32/commands":
            # Web/AI 查看当前命令队列
            self._send_json(200, {"status": "ok", "queue": command_queue.peek_all(),
                                  "size": command_queue.size()})

        elif path == "/api/tools":
            # AI Agent 工具发现
            tools = [
                "esp32_status", "esp32_command", "gpio_led", "gpio_buzzer",
                "gpio_relay", "gpio_motor", "dht_read",
                "network_scan", "network_discover", "network_ping",
                "network_traceroute", "wifi_signal", "wifi_scan",
            ]
            self._send_json(200, {"tools": tools})

        else:
            self._send_json(404, {"error": "not found", "path": path})

    # ---------- POST ----------
    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        data = self._read_json()
        if data is None:
            self._send_json(400, {"error": "invalid JSON"})
            return

        if path == "/esp32/status":
            # ESP32 上报状态
            updated = status_store.update(data)
            logger.info("ESP32 状态已更新: online=%s", updated.get("online"))
            self._send_json(200, {"status": "ok", "received": True})

        elif path == "/esp32/command":
            # Web/AI 提交控制命令
            action = data.get("action")
            if not action:
                self._send_json(400, {"error": "缺少 action 字段"})
                return
            item = command_queue.put(data)
            self._send_json(200, {"status": "ok", "queued": True, "command_id": item["id"]})

        else:
            self._send_json(404, {"error": "not found", "path": path})

    def log_message(self, format: str, *args) -> None:
        # 重写日志，使用统一 logger（仅记录非健康检查请求）
        if "/health" not in args[0]:
            logger.debug("HTTP %s", args[0])


class PiBridge:
    """树莓派桥接服务器封装"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, blocking: bool = True) -> None:
        """启动 HTTP 服务"""
        self._server = HTTPServer((self.host, self.port), BridgeHandler)
        logger.info("桥接服务器启动: http://%s:%d", self.host, self.port)
        logger.info("  端点: POST /esp32/status, POST/GET /esp32/command, GET /health")
        if blocking:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                logger.info("收到中断信号，正在关闭服务器...")
                self.stop()
        else:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """停止 HTTP 服务"""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            logger.info("桥接服务器已停止")


def run_bridge(host: str = None, port: int = None) -> None:
    """独立运行入口"""
    host = host or os.environ.get("BRIDGE_HOST", "0.0.0.0")
    port = port or int(os.environ.get("BRIDGE_PORT", "8080"))
    bridge = PiBridge(host=host, port=port)
    bridge.start(blocking=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    run_bridge()
