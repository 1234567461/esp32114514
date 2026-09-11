"""
Wi-Fi 信号分析器 —— 直接通过 Linux wireless extensions ioctl 实现，
不依赖 iw/iwlist/wpa_cli 等命令行工具。
"""
import socket
import struct
import fcntl
import array
from typing import List, Dict

SIOCGIWSCAN = 0x8B18
SIOCGIWAP = 0x8B17
SIOCGIWESSID = 0x8B1B
IW_ESSID_ON = 0x0001


class WifiAnalyzer:
    def __init__(self, iface: str = "wlan0"):
        self.iface = iface
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _ioctl(self, request, iface, data=b"\x00" * 4096):
        ifname = iface[:15].encode().ljust(16, b"\x00")
        payload = ifname + data
        try:
            return fcntl.ioctl(self.sock, request, payload)
        except OSError:
            return None

    def scan(self) -> List[Dict]:
        results = []
        self._ioctl(SIOCGIWSCAN, self.iface)
        import time
        time.sleep(2)
        current = self._read_proc_net_wireless()
        if current:
            results.append(current)
        scan_results = self._get_scan_results()
        if scan_results:
            results.extend(scan_results)
        return results

    def _read_proc_net_wireless(self) -> Dict:
        try:
            with open("/proc/net/wireless") as f:
                lines = f.readlines()
            if len(lines) < 3:
                return {}
            parts = lines[2].split()
            iface = parts[0].rstrip(":")
            if iface != self.iface:
                for line in lines[2:]:
                    p = line.split()
                    if p and p[0].rstrip(":") == self.iface:
                        parts = p
                        break
            if len(parts) >= 5:
                return {
                    "interface": parts[0].rstrip(":"),
                    "status": parts[1],
                    "link_quality": parts[2],
                    "signal_level_dbm": int(float(parts[3])),
                    "noise_level_dbm": int(float(parts[4])),
                    "discarded_packets": parts[5] if len(parts) > 5 else "0",
                }
        except (OSError, ValueError, IndexError):
            pass
        return {}

    def _get_scan_results(self) -> List[Dict]:
        results = []
        ifname = self.iface[:15].encode().ljust(16, b"\x00")
        buf = array.array("B", b"\x00" * 4096)
        ptr_addr = buf.buffer_info()[0]
        data = struct.pack("QIH", ptr_addr, 4096, 0)
        payload = ifname + data
        try:
            fcntl.ioctl(self.sock, SIOCGIWSCAN, payload)
        except OSError:
            pass
        return results

    def get_current_bssid(self) -> str:
        ifname = self.iface[:15].encode().ljust(16, b"\x00")
        data = b"\x00" * 16
        payload = ifname + data
        try:
            result = fcntl.ioctl(self.sock, SIOCGIWAP, payload)
            mac_bytes = result[18:24]
            return ":".join(f"{b:02x}" for b in mac_bytes)
        except OSError:
            return "00:00:00:00:00:00"

    def get_essid(self) -> str:
        ifname = self.iface[:15].encode().ljust(16, b"\x00")
        buf = array.array("B", b"\x00" * 33)
        ptr_addr = buf.buffer_info()[0]
        data = struct.pack("QIH", ptr_addr, 32, IW_ESSID_ON)
        payload = ifname + data
        try:
            fcntl.ioctl(self.sock, SIOCGIWESSID, payload)
            return buf.tobytes().split(b"\x00")[0].decode("utf-8", errors="replace")
        except OSError:
            return ""

    def get_signal_quality(self) -> Dict:
        info = self._read_proc_net_wireless()
        return {
            "ssid": self.get_essid(),
            "bssid": self.get_current_bssid(),
            **info,
        }

    def close(self):
        self.sock.close()


if __name__ == "__main__":
    import json
    import sys
    iface = sys.argv[1] if len(sys.argv) > 1 else "wlan0"
    wa = WifiAnalyzer(iface)
    print(json.dumps(wa.get_signal_quality(), indent=2, ensure_ascii=False))
    wa.close()
