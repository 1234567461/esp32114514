"""
树莓派网络工具封装模块
对 network_scanner 模块进行统一封装，提供：
  - 端口扫描 scan_ports
  - 主机发现 discover_network
  - 连通性 ping
  - 路由追踪 traceroute
  - Wi-Fi 信号 wifi_signal
全部基于纯 Python socket 实现，不依赖 nmap/aircrack 等外部工具，
仅用于自有网络的资产盘点与连通性诊断。
"""
import os
import sys
from typing import Dict, List, Any, Optional

# 将项目根目录加入 sys.path，以便导入 network_scanner 包
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from network_scanner.scanner import NetworkScanner, COMMON_PORTS  # noqa: E402
from network_scanner.connectivity_monitor import ConnectivityMonitor  # noqa: E402
from network_scanner.wifi_analyzer import WifiAnalyzer  # noqa: E402


class PiNetwork:
    """网络工具统一封装类。

    内部持有 NetworkScanner / ConnectivityMonitor / WifiAnalyzer 实例，
    对外暴露简洁的方法，所有方法返回 dict（或包含 dict 的列表），
    出错时返回带 error 字段的 dict，不抛出异常。
    """

    def __init__(self,
                 timeout: float = 1.0,
                 max_workers: int = 32,
                 wifi_iface: Optional[str] = None):
        """初始化网络工具。

        :param timeout: socket 超时（秒）
        :param max_workers: 扫描并发线程数
        :param wifi_iface: Wi-Fi 网卡名，默认从环境变量 WIFI_IFACE 读取或 wlan0
        """
        iface = wifi_iface or os.environ.get("WIFI_IFACE", "wlan0")
        self._scanner = NetworkScanner(timeout=timeout, max_workers=max_workers)
        self._monitor = ConnectivityMonitor(timeout=max(timeout, 2.0))
        self._wifi = WifiAnalyzer(iface)
        self._wifi_iface = iface

    # -------------------- 端口扫描 --------------------
    def scan_ports(self, ip: str, ports: Optional[List[int]] = None) -> Dict:
        """对指定 IP 进行 TCP 端口扫描。

        :param ip: 目标 IP
        :param ports: 端口列表，缺省扫描常见端口
        :return: {"ip": ..., "open_ports": [...]}
        """
        if not ip:
            return {"status": "error", "message": "缺少目标 IP"}
        try:
            if ports is None:
                ports = list(COMMON_PORTS.keys())
            ports = [int(p) for p in ports]
            return self._scanner.scan_host_ports(ip, ports)
        except Exception as e:
            return {"status": "error", "message": f"端口扫描失败: {e}", "ip": ip}

    # -------------------- 主机发现 --------------------
    def discover_network(self, cidr: str = "192.168.1.0/24") -> Dict:
        """发现指定子网内存活的主机及开放端口。

        :param cidr: 目标网段 CIDR，例如 192.168.1.0/24
        :return: {"hosts": [...]}
        """
        if not cidr:
            return {"status": "error", "message": "缺少 CIDR 参数"}
        try:
            hosts = self._scanner.discover_network(cidr)
            return {"status": "ok", "cidr": cidr, "hosts": hosts, "count": len(hosts)}
        except Exception as e:
            return {"status": "error", "message": f"主机发现失败: {e}", "cidr": cidr}

    # -------------------- Ping 连通性 --------------------
    def ping(self, host: str, count: int = 5, interval: float = 0.5) -> Dict:
        """对目标主机执行 ping 连通性测试，返回丢包率与延迟统计。

        :param host: 目标主机名或 IP
        :param count: 发送次数
        :param interval: 发送间隔（秒）
        :return: ping 统计 dict
        """
        if not host:
            return {"status": "error", "message": "缺少目标主机"}
        try:
            count = max(1, int(count))
            return self._monitor.ping_stats(host, count=count, interval=interval)
        except Exception as e:
            return {"status": "error", "message": f"Ping 失败: {e}", "host": host}

    # -------------------- Traceroute 路由追踪 --------------------
    def traceroute(self, host: str, max_hops: int = 30) -> Dict:
        """追踪到目标主机的网络路由路径。

        :param host: 目标主机名或 IP
        :param max_hops: 最大跳数
        :return: {"hops": [...]}
        """
        if not host:
            return {"status": "error", "message": "缺少目标主机"}
        try:
            hops = self._monitor.traceroute(host, max_hops=max_hops)
            return {"status": "ok", "host": host, "hops": hops}
        except Exception as e:
            return {"status": "error", "message": f"路由追踪失败: {e}", "host": host}

    # -------------------- Wi-Fi 信号 --------------------
    def wifi_signal(self) -> Dict:
        """获取当前 Wi-Fi 连接的信号质量。

        :return: 信号质量 dict，包含 ssid/bssid/signal_level_dbm 等
        """
        try:
            info = self._wifi.get_signal_quality()
            info["status"] = "ok"
            info["interface"] = self._wifi_iface
            return info
        except Exception as e:
            return {"status": "error", "message": f"Wi-Fi 信号获取失败: {e}",
                    "interface": self._wifi_iface}

    # -------------------- 工具信息 --------------------
    def get_info(self) -> Dict:
        """返回网络工具配置信息。"""
        return {
            "timeout": self._scanner.timeout,
            "max_workers": self._scanner.max_workers,
            "wifi_iface": self._wifi_iface,
            "common_ports": list(COMMON_PORTS.keys()),
        }

    def close(self) -> Dict:
        """释放 Wi-Fi 分析器持有的 socket。"""
        try:
            self._wifi.close()
            return {"status": "ok", "message": "网络工具已释放"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import json
    net = PiNetwork()
    print(json.dumps(net.get_info(), ensure_ascii=False, indent=2))
    print(json.dumps(net.wifi_signal(), ensure_ascii=False, indent=2))
    net.close()
