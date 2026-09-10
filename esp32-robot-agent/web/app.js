// ESP32 Robot Agent Web 控制台前端逻辑

function robotCmd(action, extra = {}) {
  const params = new URLSearchParams({ action, ...extra });
  if (action !== "arm") {
    params.set("speed", document.getElementById("speed").value);
  }
  fetch(`/api/robot/command?${params}`)
    .then(r => r.json())
    .then(d => console.log("命令已下发:", d));
}

function refreshRobotStatus() {
  fetch("/api/robot/status")
    .then(r => r.json())
    .then(d => {
      const box = document.getElementById("robot-status");
      box.innerHTML = `
        <p>IP: ${d.ip || "--"}</p>
        <p>RSSI: ${d.rssi || "--"} dBm</p>
        <p>距离: ${d.distance ?? "--"} cm</p>
        <p>内存: ${d.free_heap || "--"} bytes</p>
      `;
      const dot = document.getElementById("conn-status");
      const txt = document.getElementById("conn-text");
      if (d.ip) {
        dot.classList.add("online");
        txt.textContent = "ESP32 在线";
      } else {
        dot.classList.remove("online");
        txt.textContent = "ESP32 离线";
      }
    })
    .catch(() => {
      document.getElementById("conn-status").classList.remove("online");
      document.getElementById("conn-text").textContent = "ESP32 离线";
    });
}

function scanPorts() {
  const ip = document.getElementById("scan-ip").value.trim();
  const ports = document.getElementById("scan-ports").value.trim();
  if (!ip) { alert("请输入目标 IP"); return; }
  const box = document.getElementById("scan-result");
  box.textContent = "扫描中...";
  fetch(`/api/network/scan?ip=${encodeURIComponent(ip)}&ports=${encodeURIComponent(ports)}`)
    .then(r => r.json())
    .then(d => { box.textContent = JSON.stringify(d, null, 2); })
    .catch(e => { box.textContent = "错误: " + e.message; });
}

function discoverHosts() {
  const cidr = document.getElementById("scan-cidr").value.trim();
  const box = document.getElementById("scan-result");
  box.textContent = "发现主机中...";
  fetch(`/api/network/discover?cidr=${encodeURIComponent(cidr)}`)
    .then(r => r.json())
    .then(d => { box.textContent = JSON.stringify(d, null, 2); })
    .catch(e => { box.textContent = "错误: " + e.message; });
}

function pingHost() {
  const host = document.getElementById("ping-host").value.trim();
  const count = document.getElementById("ping-count").value;
  const box = document.getElementById("ping-result");
  box.textContent = "Ping 中...";
  fetch(`/api/network/ping?host=${encodeURIComponent(host)}&count=${count}`)
    .then(r => r.json())
    .then(d => {
      box.textContent = `主机: ${d.host}\n发送: ${d.sent}  接收: ${d.received}\n丢包率: ${d.loss_percent}%\n`;
      if (d.avg_ms !== undefined) {
        box.textContent += `最小: ${d.min_ms}ms  最大: ${d.max_ms}ms  平均: ${d.avg_ms}ms`;
      }
    })
    .catch(e => { box.textContent = "错误: " + e.message; });
}

function traceroute() {
  const host = document.getElementById("ping-host").value.trim();
  const box = document.getElementById("ping-result");
  box.textContent = "路由追踪中...";
  fetch(`/api/network/traceroute?host=${encodeURIComponent(host)}`)
    .then(r => r.json())
    .then(d => {
      let lines = `追踪到 ${host}:\n`;
      d.hops.forEach(h => {
        lines += `${h.hop}. ${h.ip}  ${h.rtt_ms ?? "*"}ms\n`;
      });
      box.textContent = lines;
    })
    .catch(e => { box.textContent = "错误: " + e.message; });
}

function getWifiSignal() {
  fetch("/api/wifi/signal")
    .then(r => r.json())
    .then(d => {
      const box = document.getElementById("wifi-info");
      box.innerHTML = `
        <p>SSID: ${d.ssid || "--"}</p>
        <p>BSSID: ${d.bssid || "--"}</p>
        <p>信号强度: ${d.signal_level_dbm ?? "--"} dBm</p>
        <p>噪声: ${d.noise_level_dbm ?? "--"} dBm</p>
        <p>连接质量: ${d.link_quality || "--"}</p>
      `;
    });
}

function gpioLed(on) {
  fetch(`/api/gpio/led?on=${on ? 1 : 0}`)
    .then(r => r.json())
    .then(d => console.log(d));
}

function readDHT() {
  fetch("/api/gpio/dht")
    .then(r => r.json())
    .then(d => {
      document.getElementById("dht-result").textContent =
        `温度: ${d.temperature ?? "--"}°C\n湿度: ${d.humidity ?? "--"}%`;
    });
}

// 定时刷新
setInterval(refreshRobotStatus, 3000);
refreshRobotStatus();
