"""
树莓派网络工具统一封装
=====================
封装项目内 network_scanner 下的三个模块，对外提供统一调用接口：
  - scanner:              端口扫描、子网主机发现
  - connectivity_monitor: ping、traceroute、丢包率统计
  - wifi_analyzer:        Wi-Fi 信号质量、AP 扫描

所有功能仅限授权的自有网络，不包含任何攻击行为。
"""
import os
import logging
from typing import Dict, List, Optional

# 兼容直接运行与作为包导入两种情况
try:
    from network_scanner.scanner import NetworkScanner
    from network_scanner.connectivity_monitor import ConnectivityMonitor
    from network_scanner.wifi_analyzer import WifiAnalyzer
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from network_scanner.scanner import NetworkScanner
    from network_scanner.connectivity_monitor import ConnectivityMonitor
    from network_scanner.wifi_analyzer import WifiAnalyzer

logger = logging.getLogger("pi_network")


class PiNetwork:
    """树莓派侧网络工具统一接口，封装 scanner / monitor / wifi"""

    def __init__(self, wifi_iface: str = "wlan0", scan_timeout: float = 1.0,
                 max_workers: int = 32, ping_timeout: float = 2.0):
        """
        初始化三个网络工具实例。
        :param wifi_iface: Wi-Fi 网卡接口名
        :param scan_timeout: 端口扫描超时（秒）
        :param max_workers: 扫描并发线程数
        :param ping_timeout: ping 超时（秒）
        """
        self.scanner = NetworkScanner(timeout=scan_timeout, max_workers=max_workers)
        self.monitor = ConnectivityMonitor(timeout=ping_timeout)
        self.wifi_iface = wifi_iface
        self.wifi = WifiAnalyzer(iface=wifi_iface)
        logger.info("PiNetwork 初始化完成 (wifi_iface=%s)", wifi_iface)

    # ---------------- 端口扫描 ----------------
    def scan_ports(self, ip: str, ports: Optional[List[int]] = None) -> Dict:
        """
        扫描指定主机的端口（TCP connect + banner grab）。
        :param ip: 目标 IP
        :param ports: 端口列表，None 则扫描常见端口
        """
        try:
            if ports is None:
                ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                         3306, 3389, 5432, 6379, 8080, 8443, 27017]
            result = self.scanner.scan_host_ports(ip, ports)
            return {"status": "ok", "ip": ip, "open_ports": result.get("open_ports", [])}
        except Exception as e:
            logger.error("端口扫描失败 %s: %s", ip, e)
            return {"status": "error", "ip": ip, "message": str(e)}

    def discover_network(self, cidr: str = "192.168.1.0/24") -> Dict:
        """
        发现子网内的存活主机及其常用开放端口。
        :param cidr: 目标子网 CIDR（仅限自有授权网络）
        """
        try:
            hosts = self.scanner.discover_network(cidr)
            return {"status": "ok", "cidr": cidr, "hosts": hosts, "count": len(hosts)}
        except Exception as e:
            logger.error("子网发现失败 %s: %s", cidr, e)
            return {"status": "error", "cidr": cidr, "message": str(e)}

    # ---------------- 连通性监控 ----------------
    def ping(self, host: str, count: int = 5, interval: float = 0.5) -> Dict:
        """
        对目标主机连续 ping，统计延迟与丢包率。
        """
        try:
            stats = self.monitor.ping_stats(host, count=count, interval=interval)
            return {"status": "ok", **stats}
        except Exception as e:
            logger.error("Ping 失败 %s: %s", host, e)
            return {"status": "error", "host": host, "message": str(e)}

    def ping_once(self, host: str) -> Dict:
        """单次 ping，返回往返延迟(ms)"""
        try:
            rtt = self.monitor.ping_once(host)
            if rtt is None:
                return {"status": "error", "host": host, "message": "超时或不可达"}
            return {"status": "ok", "host": host, "rtt_ms": round(rtt, 2)}
        except Exception as e:
            logger.error("Ping once 失败 %s: %s", host, e)
            return {"status": "error", "host": host, "message": str(e)}

    def traceroute(self, host: str, max_hops: int = 30) -> Dict:
        """
        路由追踪（递增 TTL）。
        注意：需要 root 权限；无权限时返回提示。
        """
        try:
            hops = self.monitor.traceroute(host, max_hops=max_hops)
            return {"status": "ok", "host": host, "hops": hops}
        except Exception as e:
            logger.error("Traceroute 失败 %s: %s", host, e)
            return {"status": "error", "host": host, "message": str(e)}

    # ---------------- Wi-Fi 分析 ----------------
    def wifi_signal(self) -> Dict:
        """获取当前 Wi-Fi 信号质量（SSID、BSSID、信号强度、噪声）"""
        try:
            info = self.wifi.get_signal_quality()
            return {"status": "ok", **info}
        except Exception as e:
            logger.error("Wi-Fi 信号获取失败: %s", e)
            return {"status": "error", "message": str(e)}

    def wifi_scan(self) -> Dict:
        """扫描周围 Wi-Fi AP 列表"""
        try:
            results = self.wifi.scan()
            return {"status": "ok", "interface": self.wifi_iface, "aps": results}
        except Exception as e:
            logger.error("Wi-Fi 扫描失败: %s", e)
            return {"status": "error", "message": str(e)}

    def wifi_essid(self) -> Dict:
        """获取当前连接的 SSID"""
        try:
            ssid = self.wifi.get_essid()
            return {"status": "ok", "ssid": ssid}
        except Exception as e:
            logger.error("获取 ESSID 失败: %s", e)
            return {"status": "error", "message": str(e)}

    # ---------------- 资源清理 ----------------
    def cleanup(self) -> None:
        """释放 Wi-Fi analyzer 的 socket 资源"""
        try:
            self.wifi.close()
            logger.info("PiNetwork 资源已释放")
        except Exception as e:
            logger.error("PiNetwork 清理失败: %s", e)
