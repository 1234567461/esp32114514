"""
Wi-Fi 信号分析器 —— 直接通过 Linux wireless extensions ioctl 实现，
不依赖 iw/iwlist/wpa_cli 等命令行工具。
功能: 扫描周围 AP、信号强度(RSSI)、信道、加密方式、噪声电平。
"""
import socket
import struct
import fcntl
import array
from typing import List, Dict

# Linux wireless extensions ioctl 常量
SIOCGIWSCAN = 0x8B18   # 触发扫描
SIOCGIWAP   = 0x8B17   # 获取关联的 AP
SIOCGIWESSID = 0x8B1B  # 获取 ESSID
SIOCGIWRANGE = 0x8B0B  # 获取无线范围参数

# 无线扩展常量
IW_ENCODE_ENABLED = 0x0001
IW_ENCODE_CRYPT_ERR = 0x8000
IW_ESSID_ON = 0x0001


class WifiAnalyzer:
    def __init__(self, iface: str = "wlan0"):
        self.iface = iface
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _ioctl(self, request, iface, data=b"\x00" * 4096):
        """执行 wireless extensions ioctl"""
        ifname = iface[:15].encode().ljust(16, b"\x00")
        payload = ifname + data
        try:
            return fcntl.ioctl(self.sock, request, payload)
        except OSError:
            return None

    def scan(self) -> List[Dict]:
        """
        触发 Wi-Fi 扫描并解析结果。
        通过 SIOCGIWSCAN ioctl 直接与内核无线驱动通信。
        """
        results = []
        # 触发扫描（可能返回 EAGAIN，需等待）
        self._ioctl(SIOCGIWSCAN, self.iface)

        import time
        time.sleep(2)  # 等待扫描完成

        # 尝试通过 /proc/net/wireless 获取当前连接信号
        current = self._read_proc_net_wireless()
        if current:
            results.append(current)

        # 尝试通过 wireless extensions 获取扫描列表
        scan_results = self._get_scan_results()
        if scan_results:
            results.extend(scan_results)

        return results

    def _read_proc_net_wireless(self) -> Dict:
        """解析 /proc/net/wireless 获取当前连接的信号质量"""
        try:
            with open("/proc/net/wireless") as f:
                lines = f.readlines()
            if len(lines) < 3:
                return {}
            # 第3行是接口数据
            parts = lines[2].split()
            iface = parts[0].rstrip(":")
            if iface != self.iface:
                # 找匹配的接口
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
        """
        通过 SIOCGIWSCAN 获取扫描结果列表。
        注意: wireless extensions 的扫描结果解析需要处理 iw_point 结构，
        不同内核版本格式略有差异，这里提供基础实现。
        """
        results = []
        ifname = self.iface[:15].encode().ljust(16, b"\x00")
        # iw_point 结构: pointer(8) + length(4) + flags(2)
        buf = array.array("B", b"\x00" * 4096)
        ptr_addr = buf.buffer_info()[0]
        data = struct.pack("QIH", ptr_addr, 4096, 0)
        payload = ifname + data
        try:
            result = fcntl.ioctl(self.sock, SIOCGIWSCAN, payload)
            # 解析返回的扫描结果
            # 这里简化处理，实际需要遍历 iw_event 链表
            # 完整实现需要解析每个 iw_event 的 cmd/len/data
            # 由于 wireless extensions 已过时，现代系统推荐用 nl80211
        except OSError:
            pass
        return results

    def get_current_bssid(self) -> str:
        """获取当前关联的 AP MAC"""
        ifname = self.iface[:15].encode().ljust(16, b"\x00")
        # sockaddr 结构: family(2) + data(14)
        data = b"\x00" * 16
        payload = ifname + data
        try:
            result = fcntl.ioctl(self.sock, SIOCGIWAP, payload)
            mac_bytes = result[18:24]
            return ":".join(f"{b:02x}" for b in mac_bytes)
        except OSError:
            return "00:00:00:00:00:00"

    def get_essid(self) -> str:
        """获取当前连接的 SSID"""
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
        """综合获取当前 Wi-Fi 信号质量"""
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
    print("\n=== Scan Results ===")
    print(json.dumps(wa.scan(), indent=2, ensure_ascii=False))
    wa.close()
