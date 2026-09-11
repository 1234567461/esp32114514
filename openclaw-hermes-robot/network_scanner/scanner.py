"""
自定义网络扫描器 —— 纯 Python socket 实现，不依赖 nmap/masscan 等外部工具。
支持: 主机发现(ICMP)、TCP 端口扫描(connect)、服务识别(banner grab)。
仅用于授权的自有网络资产盘点。
"""
import socket
import struct
import threading
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

COMMON_PORTS = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 143: "imap", 443: "https", 445: "smb",
    3306: "mysql", 3389: "rdp", 5432: "postgresql", 6379: "redis",
    8080: "http-alt", 8443: "https-alt", 27017: "mongodb",
}


class NetworkScanner:
    def __init__(self, timeout: float = 1.0, max_workers: int = 64):
        self.timeout = timeout
        self.max_workers = max_workers

    def tcp_port_scan(self, ip: str, port: int) -> Optional[Dict]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((ip, port))
            banner = ""
            try:
                sock.settimeout(1.0)
                if port in (80, 8080):
                    sock.sendall(b"HEAD / HTTP/1.0\r\nHost: " + ip.encode() + b"\r\n\r\n")
                data = sock.recv(256)
                banner = data.decode("utf-8", errors="replace").strip()[:200]
            except Exception:
                pass
            return {
                "port": port,
                "service": COMMON_PORTS.get(port, "unknown"),
                "banner": banner,
            }
        except (socket.timeout, ConnectionRefusedError, OSError):
            return None
        finally:
            sock.close()

    def scan_host_ports(self, ip: str, ports: List[int]) -> Dict:
        open_ports = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(self.tcp_port_scan, ip, p): p for p in ports}
            for fut in as_completed(futures):
                result = fut.result()
                if result:
                    open_ports.append(result)
        open_ports.sort(key=lambda x: x["port"])
        return {"ip": ip, "open_ports": open_ports}

    def host_alive_ping(self, ip: str) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError:
            return self._tcp_ping(ip)
        sock.settimeout(self.timeout)
        pid = threading.get_ident() & 0xFFFF
        seq = 1
        header = struct.pack("!BBHHH", 8, 0, 0, pid, seq)
        data = b"A" * 32
        checksum = self._icmp_checksum(header + data)
        header = struct.pack("!BBHHH", 8, 0, checksum, pid, seq)
        packet = header + data
        try:
            sock.sendto(packet, (ip, 0))
            recv, _ = sock.recvfrom(1024)
            icmp_type = recv[20]
            return icmp_type == 0
        except (socket.timeout, OSError):
            return False
        finally:
            sock.close()

    def _tcp_ping(self, ip: str) -> bool:
        for port in (80, 443):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            try:
                s.connect((ip, port))
                return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                pass
            finally:
                s.close()
        return False

    @staticmethod
    def _icmp_checksum(data: bytes) -> int:
        if len(data) % 2:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            w = (data[i] << 8) + data[i + 1]
            s += w
        s = (s >> 16) + (s & 0xFFFF)
        s += (s >> 16)
        return ~s & 0xFFFF

    def discover_network(self, cidr: str) -> List[Dict]:
        network = ipaddress.ip_network(cidr, strict=False)
        hosts = [str(h) for h in network.hosts()]
        alive = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(self.host_alive_ping, h): h for h in hosts}
            for fut in as_completed(futures):
                h = futures[fut]
                if fut.result():
                    alive.append(h)
        results = []
        common = list(COMMON_PORTS.keys())
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(self.scan_host_ports, h, common): h for h in alive}
            for fut in as_completed(futures):
                results.append(fut.result())
        return results


if __name__ == "__main__":
    import json
    import sys
    scanner = NetworkScanner(timeout=1.0)
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if "/" in target:
            print(json.dumps(scanner.discover_network(target), indent=2, ensure_ascii=False))
        else:
            ports = [int(p) for p in sys.argv[2].split(",")] if len(sys.argv) > 2 else list(COMMON_PORTS.keys())
            print(json.dumps(scanner.scan_host_ports(target, ports), indent=2, ensure_ascii=False))
