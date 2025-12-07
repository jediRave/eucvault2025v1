import platform
import os
import webbrowser
import shutil
import psutil
import time


def get_system_info():
    info = {}

    # Basic system info
    info["computer_name"] = platform.node()
    info["system"] = platform.system()
    info["release"] = platform.release()
    info["version"] = platform.version()
    info["machine"] = platform.machine()
    info["processor"] = platform.processor()

    # RAM
    vm = psutil.virtual_memory()
    info["ram_total_gb"] = round(vm.total / (1024 ** 3), 2)
    info["ram_used_gb"] = round(vm.used / (1024 ** 3), 2)
    info["ram_percent"] = vm.percent

    # Disk (system drive)
    disk_path = os.path.abspath(os.sep)  # usually C:\
    total, used, free = shutil.disk_usage(disk_path)
    info["disk_total_gb"] = round(total / (1024 ** 3), 2)
    info["disk_used_gb"] = round(used / (1024 ** 3), 2)
    info["disk_free_gb"] = round(free / (1024 ** 3), 2)
    info["disk_percent"] = round(used / total * 100, 1)

    # Battery (if available)
    try:
        batt = psutil.sensors_battery()
    except Exception:
        batt = None

    if batt is not None:
        info["battery_percent"] = batt.percent
        info["battery_plugged"] = batt.power_plugged
    else:
        info["battery_percent"] = None
        info["battery_plugged"] = None

    # CPU
    info["cpu_percent"] = psutil.cpu_percent(interval=1.0)
    info["cpu_count"] = psutil.cpu_count(logical=True)
    info["cpu_per_core"] = psutil.cpu_percent(interval=1.0, percpu=True)

    # Uptime
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time
    info["uptime_hours"] = round(uptime_seconds / 3600, 1)

    # Processes
    info["process_count"] = len(psutil.pids())

    # Network throughput sample (approx "internet speed" right now)
    net1 = psutil.net_io_counters()
    time.sleep(1)
    net2 = psutil.net_io_counters()

    bytes_sent_per_s = net2.bytes_sent - net1.bytes_sent
    bytes_recv_per_s = net2.bytes_recv - net1.bytes_recv

    info["net_up_mbps"] = round((bytes_sent_per_s * 8) / (1024 ** 2), 2)
    info["net_down_mbps"] = round((bytes_recv_per_s * 8) / (1024 ** 2), 2)

    # Simple overall health scoring
    cpu = info["cpu_percent"]
    ram = info["ram_percent"]
    disk = info["disk_percent"]

    if cpu < 70 and ram < 75 and disk < 85:
        info["health_status"] = "Healthy"
        info["health_color"] = "#4CAF50"
    elif cpu < 85 and ram < 85 and disk < 90:
        info["health_status"] = "Moderate Load"
        info["health_color"] = "#FFC107"
    else:
        info["health_status"] = "High Load"
        info["health_color"] = "#F44336"

    return info


def generate_html(info):
    # Precompute chart angles for conic gradients
    cpu_angle = info["cpu_percent"] * 3.6
    ram_angle = info["ram_percent"] * 3.6
    disk_angle = info["disk_percent"] * 3.6

    # Battery text
    if info["battery_percent"] is None:
        battery_text = "No battery / Not detected"
    else:
        plugged = " (Plugged In)" if info["battery_plugged"] else ""
        battery_text = f'{info["battery_percent"]}%{plugged}'

    # Per-core CPU list HTML
    core_rows = ""
    for i, pct in enumerate(info["cpu_per_core"], start=1):
        core_rows += f"""
        <div class="core-row">
            <span>Core {i}</span>
            <div class="bar-bg">
                <div class="bar-fill" style="width:{pct}%;"></div>
            </div>
            <span class="core-pct">{pct:.0f}%</span>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Laptop Status Dashboard</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #0f172a;
            color: #e5e7eb;
            padding: 20px;
        }}
        h1 {{
            color: #38bdf8;
            margin-bottom: 5px;
        }}
        h2 {{
            color: #e5e7eb;
        }}
        .subtitle {{
            color: #9ca3af;
            margin-bottom: 20px;
        }}
        .tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }}
        .tab-btn {{
            padding: 10px 18px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #111827;
            color: #e5e7eb;
            cursor: pointer;
            font-weight: 600;
        }}
        .tab-btn.active {{
            background: #38bdf8;
            color: #0f172a;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit,minmax(260px,1fr));
            gap: 16px;
        }}
        .card {{
            background-color: #020617;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            border: 1px solid #1f2937;
        }}
        .label {{
            color: #9ca3af;
            font-size: 0.9rem;
        }}
        .value {{
            font-size: 1.1rem;
            font-weight: 600;
        }}
        .pill {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .health-pill {{
            background: #111827;
            border: 1px solid #1f2937;
        }}
        .gauge-container {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .gauge {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            margin-bottom: 8px;
        }}
        .gauge-inner {{
            position: absolute;
            width: 80px;
            height: 80px;
            background: #020617;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }}
        .gauge-label {{
            font-size: 0.8rem;
            color: #9ca3af;
        }}
        .gauge-value {{
            font-size: 1.1rem;
            font-weight: 700;
        }}
        .core-row {{
            display: grid;
            grid-template-columns: 60px 1fr 50px;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }}
        .bar-bg {{
            height: 8px;
            background: #111827;
            border-radius: 999px;
            overflow: hidden;
        }}
        .bar-fill {{
            height: 100%;
            background: linear-gradient(90deg,#22c55e,#eab308,#ef4444);
        }}
        .core-pct {{
            text-align: right;
            font-size: 0.85rem;
            color: #9ca3af;
        }}
        .muted {{
            color: #6b7280;
            font-size: 0.85rem;
        }}
        .big-number {{
            font-size: 1.8rem;
            font-weight: 700;
        }}
    </style>
</head>
<body>
    <h1>Laptop Status Dashboard</h1>
    <div class="subtitle">
        {info["computer_name"]} • {info["system"]} {info["release"]} • {info["processor"]}
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="showTab('standard')" id="btn-standard">Standard User</button>
        <button class="tab-btn" onclick="showTab('pro')" id="btn-pro">Pro User</button>
    </div>

    <!-- Standard User Tab -->
    <div class="tab-content active" id="standardTab">
        <div class="grid">
            <div class="card">
                <div class="label">Overall System Health</div>
                <div class="value" style="color:{info["health_color"]}; margin-top:4px;">
                    {info["health_status"]}
                </div>
                <div class="muted" style="margin-top:8px;">
                    Based on current CPU, RAM and disk usage.
                </div>
            </div>

            <div class="card">
                <div class="label">Internet Speed (approx, live sample)</div>
                <div class="value" style="margin-top:4px;">
                    ↓ {info["net_down_mbps"]} Mbps &nbsp;&nbsp; ↑ {info["net_up_mbps"]} Mbps
                </div>
                <div class="muted" style="margin-top:8px;">
                    This is a 1-second snapshot of current network traffic, not a full ISP speed test.
                </div>
            </div>

            <div class="card">
                <div class="label">Battery</div>
                <div class="value" style="margin-top:4px;">
                    {battery_text}
                </div>
                <div class="muted" style="margin-top:8px;">
                    If plugged in, it's safe to run heavy tasks or gaming for longer.
                </div>
            </div>

            <div class="card">
                <div class="label">Uptime</div>
                <div class="big-number" style="margin-top:4px;">
                    {info["uptime_hours"]} h
                </div>
                <div class="muted">
                    Time since last restart.
                </div>
            </div>
        </div>

        <div class="card" style="margin-top:20px;">
            <h2>Resource Usage</h2>
            <div class="gauge-container">
                <div>
                    <div class="gauge" style="background: conic-gradient(#22c55e 0deg {cpu_angle}deg, #111827 {cpu_angle}deg 360deg);">
                        <div class="gauge-inner">
                            <div class="gauge-value">{info["cpu_percent"]:.0f}%</div>
                            <div class="gauge-label">CPU</div>
                        </div>
                    </div>
                    <div class="muted">Current processor load.</div>
                </div>

                <div>
                    <div class="gauge" style="background: conic-gradient(#3b82f6 0deg {ram_angle}deg, #111827 {ram_angle}deg 360deg);">
                        <div class="gauge-inner">
                            <div class="gauge-value">{info["ram_percent"]:.0f}%</div>
                            <div class="gauge-label">RAM</div>
                        </div>
                    </div>
                    <div class="muted">
                        {info["ram_used_gb"]} / {info["ram_total_gb"]} GB in use.
                    </div>
                </div>

                <div>
                    <div class="gauge" style="background: conic-gradient(#f97316 0deg {disk_angle}deg, #111827 {disk_angle}deg 360deg);">
                        <div class="gauge-inner">
                            <div class="gauge-value">{info["disk_percent"]:.0f}%</div>
                            <div class="gauge-label">Disk</div>
                        </div>
                    </div>
                    <div class="muted">
                        {info["disk_used_gb"]} / {info["disk_total_gb"]} GB used.
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Pro User Tab -->
    <div class="tab-content" id="proTab">
        <div class="grid">
            <div class="card">
                <div class="label">CPU Overview</div>
                <div class="value" style="margin-top:4px;">
                    {info["cpu_percent"]:.0f}% load • {info["cpu_count"]} logical cores
                </div>
                <div class="muted" style="margin-top:8px;">
                    Good for spotting spikes during builds, encoding, or gaming.
                </div>
            </div>

            <div class="card">
                <div class="label">Memory</div>
                <div class="value" style="margin-top:4px;">
                    {info["ram_used_gb"]} / {info["ram_total_gb"]} GB used ({info["ram_percent"]:.0f}%)
                </div>
                <div class="muted" style="margin-top:8px;">
                    High usage can cause slowdowns, stutters or app crashes.
                </div>
            </div>

            <div class="card">
                <div class="label">Disk</div>
                <div class="value" style="margin-top:4px;">
                    {info["disk_used_gb"]} / {info["disk_total_gb"]} GB used ({info["disk_percent"]:.0f}%)
                </div>
                <div class="muted" style="margin-top:8px;">
                    Keeping at least 15–20% free is recommended for best performance.
                </div>
            </div>

            <div class="card">
                <div class="label">Processes</div>
                <div class="big-number" style="margin-top:4px;">
                    {info["process_count"]}
                </div>
                <div class="muted">
                    Total running processes (services + apps).
                </div>
            </div>
        </div>

        <div class="card" style="margin-top:20px;">
            <h2>Per-Core CPU Activity</h2>
            <div class="muted" style="margin-bottom:8px;">
                Useful to check if workloads are multi-threaded or hammering a single core.
            </div>
            {core_rows}
        </div>

        <div class="card" style="margin-top:20px;">
            <h2>Network Snapshot</h2>
            <div class="value" style="margin-top:4px;">
                ↓ {info["net_down_mbps"]} Mbps &nbsp;&nbsp; ↑ {info["net_up_mbps"]} Mbps
            </div>
            <div class="muted" style="margin-top:8px;">
                1-second sample based on OS counters. For full benchmarking, use dedicated tools
                (e.g. Speedtest) and compare over time.
            </div>
        </div>
    </div>

    <script>
        function showTab(tab) {{
            const standard = document.getElementById('standardTab');
            const pro = document.getElementById('proTab');
            const btnStandard = document.getElementById('btn-standard');
            const btnPro = document.getElementById('btn-pro');

            if (tab === 'standard') {{
                standard.classList.add('active');
                pro.classList.remove('active');
                btnStandard.classList.add('active');
                btnPro.classList.remove('active');
            }} else {{
                pro.classList.add('active');
                standard.classList.remove('active');
                btnPro.classList.add('active');
                btnStandard.classList.remove('active');
            }}
        }}
    </script>
</body>
</html>"""

    return html_content


def save_and_open(html):
    filename = "Laptop_Report.html"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(html)
    webbrowser.open(f"file://{os.path.realpath(filename)}")


# --- MAIN ---
data = get_system_info()
html = generate_html(data)
save_and_open(html)
