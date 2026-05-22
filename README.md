# jbd_bms-victron-bridge

> Bridge a JBD / Xiaoxiang BMS to a Victron Venus OS GX device via Bluetooth Low Energy and MQTT.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20VenusOS-lightgrey)]()

Reads a JBD (Jiabaida) Smart BMS over BLE, repackages the data into the
[`dbus-mqtt-battery`](https://github.com/mr-manuel/venus-os_dbus-mqtt-battery)
JSON schema, and publishes it to the MQTT broker of a Victron Venus OS GX
device. The battery then appears in the GX console / VRM portal as a fully
fledged battery monitor with voltage, current, SoC, cell voltages, and BMS
charge/discharge limits.

---

## Table of contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Hardware requirements](#hardware-requirements)
4. [Software requirements](#software-requirements)
5. [Repository layout](#repository-layout)
6. [Quick start](#quick-start)
7. [Installation — Venus OS (driver)](#installation--venus-os-driver)
8. [Installation — Windows publisher](#installation--windows-publisher)
9. [Installation — Linux publisher (Ubuntu / Debian)](#installation--linux-publisher-ubuntu--debian)
10. [Configuration](#configuration)
11. [Verification](#verification)
12. [Auto-start](#auto-start)
13. [Troubleshooting](#troubleshooting)
14. [Roadmap](#roadmap)
15. [Credits](#credits)
16. [License](#license)

---

## Features

- ✅ Reads JBD BMS over Bluetooth LE (no wired connection required)
- ✅ Publishes data every 5 s (configurable)
- ✅ Output format compatible with the popular `dbus-mqtt-battery` driver
- ✅ Battery appears as native device in Venus OS GX console & VRM
- ✅ Static BMS limits (max charge V/A, max discharge A) configurable
- ✅ Cell-level voltage & temperature data forwarded
- ✅ Diagnostic BLE scanner included
- ✅ Cross-platform: runs on Windows, Ubuntu, Debian, Raspberry Pi
- ✅ Single-file Python script — no compile step, easy to audit

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   ┌─────────────┐                ┌──────────────────────┐    │
│   │  JBD BMS    │                │   Venus OS GX        │    │
│   │ (Xiaoxiang) │                │   (Cerbo / RPi)      │    │
│   │             │                │                      │    │
│   │  ┌───────┐  │   BLE notify   │   ┌──────────────┐   │    │
│   │  │ FF02  │◄─┼────────────────┼──►│ Mosquitto    │   │    │
│   │  │ FF01  │  │   (GATT)       │   │  :1883       │   │    │
│   │  └───────┘  │                │   └──────┬───────┘   │    │
│   └─────────────┘                │          │           │    │
│         ▲                        │   subscribe          │    │
│         │                        │   battery/jbd_jbd1   │    │
│   ┌─────┴────────┐               │          │           │    │
│   │ Host running │   MQTT pub    │          ▼           │    │
│   │ this script  │──────────────►│  dbus-mqtt-battery   │    │
│   │ (Windows /   │   topic       │  driver              │    │
│   │  Linux /     │  battery/...  │          │           │    │
│   │  VenusOS)    │               │          ▼           │    │
│   └──────────────┘               │  com.victronenergy.  │    │
│                                  │  battery.mqtt_       │    │
│                                  │  battery_100         │    │
│                                  │          │           │    │
│                                  │          ▼           │    │
│                                  │   GX Console / VRM   │    │
│                                  └──────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

Two moving parts:

| Component | Where it runs | What it does |
|-----------|---------------|--------------|
| **Publisher** (`jbd_venus_mqtt.py`) | Any host with BLE in range of the BMS | Reads BMS, publishes JSON to MQTT |
| **Driver** (`dbus-mqtt-battery` by mr-manuel) | Venus OS GX device | Subscribes to MQTT, exposes battery on dbus |

---

## Hardware requirements

| Item | Tested with | Notes |
|------|-------------|-------|
| BMS | JBD 4S 100A (sold as "Xiaoxiang") with BLE module | Any JBD BLE BMS using FF01/FF02 GATT chars |
| Battery | 4S LFP 280 Ah (LF280K cells) | Any pack the BMS supports |
| GX device | Raspberry Pi running Venus OS v3.34 | Cerbo GX, CCGX, MultiPlus-II GX should all work |
| Host running publisher | Windows 11 laptop (Intel BLE), Ubuntu 22.04, RPi 4 | Anything with Python ≥ 3.8 and BLE |
| Network | Same LAN or Tailscale | Publisher needs TCP access to broker port 1883 |

---

## Software requirements

- **Python** ≥ 3.8
- **bleak** ≥ 0.20 (BLE library)
- **paho-mqtt** ≥ 1.6 (works with v2.x)
- **Venus OS** ≥ 3.00 (for the driver — older versions may work but untested)

Install via `pip install -r requirements.txt`.

---

## Repository layout

```
jbd_bms-victron-bridge/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── requirements.txt
├── .gitignore
├── jbd_venus_mqtt.py          # Main publisher script
├── install/                   # Convenience installers
│   ├── README.md
│   ├── install_linux.sh
│   ├── install_windows.ps1
│   └── jbd-venus-bridge.service
├── scripts/
│   └── ble_scan.py            # Diagnostic BLE scanner
└── docs/
    ├── architecture.md
    └── troubleshooting.md
```

---

## Quick start

For users in a hurry — assumes Venus OS, Windows host, and an existing JBD BMS in BLE range.

```bash
# 1. On Venus OS — install dbus-mqtt-battery driver
ssh root@<venus-ip>
cd /data/etc
wget -O dmb.zip https://github.com/mr-manuel/venus-os_dbus-mqtt-battery/archive/refs/heads/master.zip
unzip -o dmb.zip
mv venus-os_dbus-mqtt-battery-master/dbus-mqtt-battery ./dbus-mqtt-battery
cd dbus-mqtt-battery
cp config.sample.ini config.ini
# edit config.ini: broker_address=127.0.0.1, topic=battery/jbd_jbd1
bash install.sh
```

```powershell
# 2. On Windows host — install publisher
git clone https://github.com/Ab0u/jbd_bms-victron-bridge.git
cd jbd_bms-victron-bridge
.\install\install_windows.ps1
# Edit jbd_venus_mqtt.py: set BMS_MAC, BMS_PIN and MQTT_HOST
python jbd_venus_mqtt.py
```

Or on Linux:

```bash
git clone https://github.com/Ab0u/jbd_bms-victron-bridge.git
cd jbd_bms-victron-bridge
bash install/install_linux.sh
# Edit jbd_venus_mqtt.py
.venv/bin/python jbd_venus_mqtt.py
```

Battery should be visible in GX console within 60 s.

> 💡 The `install/` directory contains convenience scripts that wrap the
> manual steps below — see [`install/README.md`](install/README.md). The
> step-by-step instructions in the sections that follow remain the
> authoritative reference.

---

## Installation — Venus OS (driver)

This installs the [`dbus-mqtt-battery`](https://github.com/mr-manuel/venus-os_dbus-mqtt-battery)
driver on the GX device. It is the component that turns MQTT data into a real
Victron battery service on dbus.

### Step 1 — SSH into Venus

```bash
ssh root@<venus-ip>
```

You should land at `root@<hostname>:~#`.

### Step 2 — Verify the local MQTT broker

Venus OS ships with a working Mosquitto broker. Confirm it listens on port
1883:

```bash
netstat -ln | grep ':1883'
```

Expected:

```
tcp        0      0 0.0.0.0:1883            0.0.0.0:*               LISTEN
tcp        0      0 :::1883                 :::*                    LISTEN
```

If the broker is bound to `127.0.0.1` only and you want to publish from a
different host, you may have to add a listener config — see
[Troubleshooting](docs/troubleshooting.md).

### Step 3 — Download and unpack the driver

```bash
mkdir -p /data/etc
cd /data/etc
wget -O dbus-mqtt-battery.zip \
  https://github.com/mr-manuel/venus-os_dbus-mqtt-battery/archive/refs/heads/master.zip
unzip -o dbus-mqtt-battery.zip
mv venus-os_dbus-mqtt-battery-master/dbus-mqtt-battery ./dbus-mqtt-battery
rm -rf venus-os_dbus-mqtt-battery-master dbus-mqtt-battery.zip
```

> ⚠️ Note: the directory **must** end up at `/data/etc/dbus-mqtt-battery/`
> (not `/data/etc/venus-os_dbus-mqtt-battery-master/...`) because the
> `service/run` script hard-codes that path.

### Step 4 — Configure the driver

```bash
cd /data/etc/dbus-mqtt-battery
cp config.sample.ini config.ini
```

Edit `config.ini`:

```ini
[DEFAULT]
device_name     = JBD LFP 12V
device_instance = 100
timeout         = 60

[MQTT]
broker_address = 127.0.0.1
broker_port    = 1883
topic          = battery/jbd_jbd1
```

Verify:

```bash
grep -E '^(broker_address|broker_port|topic|device_name|device_instance|timeout)' config.ini
```

### Step 5 — Install

```bash
bash install.sh
```

This creates the daemontools symlink `/service/dbus-mqtt-battery → ...` and
appends a re-install line to `/data/rc.local` so the install survives Venus
firmware updates.

### Step 6 — Verify the service

```bash
sleep 5 && svstat /service/dbus-mqtt-battery
tail -n 20 /var/log/dbus-mqtt-battery/current
```

Expected: service `up` with rising uptime, log shows
`WARNING:root:Waiting since 60 seconds for receiving first data...` — this is
normal until the publisher starts sending data.

---

## Installation — Windows publisher

### Step 1 — Install Python 3

Download from <https://www.python.org/downloads/> (≥ 3.8). During install,
**check** the box "Add Python to PATH".

Verify in PowerShell:

```powershell
python --version
```

### Step 2 — Clone the repo

```powershell
git clone https://github.com/Ab0u/jbd_bms-victron-bridge.git
cd jbd_bms-victron-bridge
```

(Or download the ZIP from GitHub and extract.)

### Step 3 — Install dependencies

```powershell
pip install -r requirements.txt
```

### Step 4 — Find the BMS MAC address

```powershell
python scripts\ble_scan.py
```

Expected output (excerpt):

```
A4:C1:37:21:E7:0A  name=Zalaqa  RSSI=-65
```

`name=` varies (often `xiaoxiang BMS`, `JBD-XX`, or whatever was configured in
the app). RSSI < -85 means the host is probably too far away — move closer.

### Step 5 — Configure

Open `jbd_venus_mqtt.py` in a text editor (Notepad, VS Code, …) and edit the
config block near the top:

```python
BMS_MAC   = "A4:C1:37:21:E7:0A"        # from ble_scan.py
MQTT_HOST = "192.168.0.125"            # IP of Venus OS GX
MQTT_PORT = 1883
MQTT_TOPIC = "battery/jbd_jbd1"        # must match driver config.ini

INSTALLED_CAPACITY_AH = 280.0
MAX_CHARGE_VOLTAGE    = 14.0
MAX_CHARGE_CURRENT    = 50
MAX_DISCHARGE_CURRENT = 150
```

### Step 6 — Run

```powershell
python jbd_venus_mqtt.py
```

You should see roughly every 5 s:

```
[15:12:26] V=13.48 I=+15.25A SOC=79% T=21.7C dV=4.0mV -> publish OK
```

---

## Installation — Linux publisher (Ubuntu / Debian)

Same flow as Windows, with package-manager differences.

### Step 1 — System packages

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git bluetooth bluez
```

### Step 2 — Clone the repo

```bash
git clone https://github.com/Ab0u/jbd_bms-victron-bridge.git
cd jbd_bms-victron-bridge
```

### Step 3 — Create a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 4 — Bluetooth permissions

On most desktops Bluetooth works out of the box. On headless servers you may
have to enable the service:

```bash
sudo systemctl enable --now bluetooth
```

If `BleakDBusError: ... not authorized`, add your user to the `bluetooth`
group and re-login:

```bash
sudo usermod -aG bluetooth $USER
```

### Step 5 — Discover the BMS

```bash
python scripts/ble_scan.py
```

### Step 6 — Configure and run

Edit `jbd_venus_mqtt.py` as in the Windows section, then:

```bash
python jbd_venus_mqtt.py
```

---

## Configuration

All settings are at the top of `jbd_venus_mqtt.py`.

| Variable | Purpose | Typical value |
|---------|---------|--------------|
| `BMS_MAC` | Bluetooth MAC address of the BMS | `A4:C1:37:21:E7:0A` |
| `BMS_PIN` | 6-digit numeric pin set in the JBD / Xiaoxiang app | `000000` (factory default) |
| `MQTT_HOST` | IP / hostname of MQTT broker | `192.168.0.125` |
| `MQTT_PORT` | MQTT port | `1883` |
| `MQTT_TOPIC` | Topic to publish on | `battery/jbd_jbd1` |
| `MQTT_USER` / `MQTT_PASS` | MQTT credentials | `None` for anonymous |
| `POLL_INTERVAL` | Seconds between BMS reads | `5` |
| `BLE_TIMEOUT` | BLE connect timeout (s) | `20` |
| `INSTALLED_CAPACITY_AH` | Total Ah of the pack | `280.0` |
| `MAX_CHARGE_VOLTAGE` | Absorption voltage | `14.0` (4S LFP) |
| `MAX_CHARGE_CURRENT` | Max charge current the BMS will accept | `50` |
| `MAX_DISCHARGE_CURRENT` | Max discharge current the BMS will accept | `150` |

> ⚠️ The `MAX_*` values are used by Venus DVCC to throttle MPPTs / inverter.
> Set them to a safe value below the real BMS limits if you do not know them.

The topic **must** match the `topic = …` line in the driver's `config.ini`.

### BMS pin

JBD BMSes are protected by a 6-digit numeric pin that the host must present
before the BMS will accept commands. The factory default is `000000`. If you
have ever changed it via the JBD / Xiaoxiang app, set `BMS_PIN` to that
value:

```python
BMS_PIN = "123456"   # whatever you configured in the app
```

The script builds the authentication frame and checksum at startup; the
ASCII-encoded pin is hashed into the frame as

```
FF AA 15 06 <pin[0]> <pin[1]> <pin[2]> <pin[3]> <pin[4]> <pin[5]> <checksum>
```

where `<checksum> = (0x15 + 0x06 + sum(pin_bytes)) & 0xFF`.

If you forgot the pin, reset the BMS to factory defaults via the JBD app
("Restore Manufacturer Settings") — this restores `000000`.

---

## Verification

### On Venus OS

```bash
# Driver service status
svstat /service/dbus-mqtt-battery

# Live log
tail -f /var/log/dbus-mqtt-battery/current

# dbus inspection
dbus -y com.victronenergy.battery.mqtt_battery_100 / GetValue | head -n 30
```

Expected dbus output (excerpt):

```python
{'Capacity': 221.2,
 'Connected': 1,
 'ConsumedAmphours': 58.8,
 'CustomName': 'JBD LFP 12V',
 'Dc/0/Current': 40.34,
 'Dc/0/Power': 547.4,
 'Dc/0/Temperature': 21.8,
 'Dc/0/Voltage': 13.57,
 'DeviceInstance': 100,
 'Soc': 79,
 …}
```

### In the GX console

Open `http://<venus-ip>/` and look for the battery tile in the dashboard, or
in **Device List → JBD LFP 12V**.

### In the VRM portal

After 5–15 min the device appears in <https://vrm.victronenergy.com/> under
your installation's "Advanced" tab and dashboard.

---

## Auto-start

### Linux (systemd)

Create `/etc/systemd/system/jbd-venus-bridge.service`:

```ini
[Unit]
Description=JBD BMS to Victron Venus OS MQTT bridge
After=network-online.target bluetooth.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/jbd_bms-victron-bridge
ExecStart=/home/pi/jbd_bms-victron-bridge/.venv/bin/python /home/pi/jbd_bms-victron-bridge/jbd_venus_mqtt.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activate:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jbd-venus-bridge.service
sudo systemctl status jbd-venus-bridge.service
```

### Windows (Task Scheduler)

1. Open *Task Scheduler*
2. Create Basic Task → name "JBD Venus Bridge"
3. Trigger: "When the computer starts"
4. Action: "Start a program"
   - Program: `pythonw.exe` (note: `pythonw`, not `python`, to hide console)
   - Arguments: `C:\path\to\jbd_venus_mqtt.py`
5. Open task properties → check "Run whether user is logged on or not"
6. Settings → "If the task fails, restart every 1 minute, up to 999 times"

### Venus OS (run publisher locally on GX)

If your Venus device has BLE in range of the BMS, copy the publisher there
and add it to `/data/rc.local`:

```bash
# Publisher auto-start
nohup python3 /data/jbd_venus_mqtt.py >/var/log/jbd_publisher.log 2>&1 &
```

---

## Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for a longer guide.
Short version:

| Symptom | Most likely cause | Fix |
|---------|-------------------|-----|
| `Device … was not found` | BMS not advertising or out of range | Open the JBD app once to wake it, or trigger load on the pack |
| Driver log keeps timing out | Publisher not running or wrong topic | Confirm topic match between `jbd_venus_mqtt.py` and `config.ini` |
| `dbus.exceptions … no such name` | Driver crash-looping | `tail /var/log/dbus-mqtt-battery/current` for Python errors |
| Battery shows in GX but SoC stuck | Publisher hung — check Bleak version | Update bleak, restart publisher |
| `python: can't open file …` | Driver directory in wrong path | Must be `/data/etc/dbus-mqtt-battery/`, not `…-master/...` |

---

## Roadmap

- [ ] BMS auto-discovery (scan & match on name pattern)
- [ ] Multi-BMS support (publish to different topics)
- [ ] Optional MaxChargeCurrent / MaxDischargeCurrent read directly from BMS
- [ ] Native Venus OS service (no separate publisher host)
- [ ] Home Assistant MQTT discovery payload
- [ ] Prometheus exporter

Contributions welcome — open an issue first to discuss large changes.

---

## Credits

- [@mr-manuel](https://github.com/mr-manuel) for the excellent
  [`dbus-mqtt-battery`](https://github.com/mr-manuel/venus-os_dbus-mqtt-battery)
  Venus OS driver that does the heavy lifting on the GX side.
- Victron Energy for the open Venus OS platform.
- The reverse-engineering work by the
  [overkill-solar](https://github.com/FurTrader/Overkill-Solar-BMS-Bluetooth-master)
  and Home Assistant communities on the JBD BLE protocol.

---

## License

MIT — see [`LICENSE`](LICENSE).

Copyright © 2026 M. Hajji ([@Ab0u](https://github.com/Ab0u))
