"""
连通性监控工具 —— 纯 socket 实现，不依赖 ping/mtr 等外部工具。
支持: 自定义 ICMP ping、traceroute（TTL 递增）、丢包率统计、延迟分布。
"""
import socket
import struct
import time
import threading
from typing import Dict, List, Optional


class ConnectivityMonitor:
    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout

    def ping_once(self, host: str) -> Optional[float]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError:
            return self._tcp_ping_rtt(host)
        sock.settimeout(self.timeout)
        pid = threading.get_ident() & 0xFFFF
        seq = int(time.time() * 1000) & 0xFFFF
        header = struct.pack("!BBHHH", 8, 0, 0, pid, seq)
        data = b"PING" * 8
        checksum = self._checksum(header + data)
        header = struct.pack("!BBHHH", 8, 0, checksum, pid, seq)
        packet = header + data
        send_time = time.time()
        try:
            sock.sendto(packet, (host, 0))
            recv, _ = sock.recvfrom(1024)
            rtt = (time.time() - send_time) * 1000
            return rtt
        except (socket.timeout, OSError):
            return None
        finally:
            sock.close()

    def _tcp_ping_rtt(self, host: str, port: int = 80) -> Optional[float]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        t0 = time.time()
        try:
            s.connect((host, port))
            return (time.time() - t0) * 1000
        except (socket.timeout, OSError):
            return None
        finally:
            s.close()

    @staticmethod
    def _checksum(data: bytes) -> int:
        if len(data) % 2:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            s += (data[i] << 8) + data[i + 1]
        s = (s >> 16) + (s & 0xFFFF)
        s += (s >> 16)
        return ~s & 0xFFFF

    def ping_stats(self, host: str, count: int = 10, interval: float = 0.5) -> Dict:
        rtts = []
        sent = 0
        received = 0
        for _ in range(count):
            sent += 1
            rtt = self.ping_once(host)
            if rtt is not None:
                received += 1
                rtts.append(rtt)
            time.sleep(interval)
        loss = (1 - received / sent) * 100 if sent else 100
        if rtts:
            return {
                "host": host,
                "sent": sent,
                "received": received,
                "loss_percent": round(loss, 2),
                "min_ms": round(min(rtts), 2),
                "max_ms": round(max(rtts), 2),
                "avg_ms": round(sum(rtts) / len(rtts), 2),
            }
        return {"host": host, "sent": sent, "received": 0, "loss_percent": 100.0}

    def traceroute(self, host: str, max_hops: int = 30) -> List[Dict]:
        hops = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError:
            return [{"error": "需要 root 权限执行 traceroute"}]
        sock.settimeout(self.timeout)
        for ttl in range(1, max_hops + 1):
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
            pid = threading.get_ident() & 0xFFFF
            header = struct.pack("!BBHHH", 8, 0, 0, pid, ttl)
            data = b"TRACE" * 6
            checksum = self._checksum(header + data)
            header = struct.pack("!BBHHH", 8, 0, checksum, pid, ttl)
            packet = header + data
            send_time = time.time()
            try:
                sock.sendto(packet, (host, 0))
                recv, addr = sock.recvfrom(1024)
                rtt = (time.time() - send_time) * 1000
                icmp_type = recv[20]
                hops.append({"hop": ttl, "ip": addr[0], "rtt_ms": round(rtt, 2), "type": icmp_type})
                if icmp_type == 0:
                    break
            except socket.timeout:
                hops.append({"hop": ttl, "ip": "*", "rtt_ms": None, "type": None})
            except OSError:
                break
        sock.close()
        return hops


if __name__ == "__main__":
    import json
    import sys
    mon = ConnectivityMonitor()
    host = sys.argv[1] if len(sys.argv) > 1 else "8.8.8.8"
    print("=== Ping Stats ===")
    print(json.dumps(mon.ping_stats(host, count=5), indent=2, ensure_ascii=False))
    print("\n=== Traceroute ===")
    print(json.dumps(mon.traceroute(host), indent=2, ensure_ascii=False))
