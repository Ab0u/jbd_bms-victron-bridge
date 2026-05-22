#!/usr/bin/env python3
"""
jbd_venus_mqtt.py — Bridge a JBD / Xiaoxiang BMS to Victron Venus OS via MQTT.

Reads pack voltage, current, SoC, cell voltages and temperatures from a JBD
BMS over Bluetooth LE and publishes them in the JSON schema expected by the
`dbus-mqtt-battery` Venus OS driver (mr-manuel).

Project : https://github.com/Ab0u/jbd_bms-victron-bridge
Author  : M. Hajji (@Ab0u)
License : MIT (see LICENSE)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

from bleak import BleakClient, BleakError
import paho.mqtt.client as mqtt

# ======================================================================
# CONFIG
# ======================================================================
BMS_MAC = "A4:C1:37:21:E7:0A"
BMS_PIN = "000000"    # 6-digit numeric pin set in the JBD/Xiaoxiang app (default 000000)

MQTT_HOST = "192.168.0.125"
MQTT_PORT = 1883
MQTT_TOPIC = "battery/jbd_jbd1"
MQTT_USER: str | None = None
MQTT_PASS: str | None = None

POLL_INTERVAL = 5     # seconds between BMS reads
BLE_TIMEOUT = 20      # BLE connect timeout (s)
NOTIFY_WAIT = 4       # per-frame wait for BMS reply (s)

# Static pack specs — adjust to your battery
INSTALLED_CAPACITY_AH = 280.0      # total Ah
MAX_CHARGE_VOLTAGE = 14.0          # absorption voltage (4S LFP ≈ 14.0–14.4)
MAX_CHARGE_CURRENT = 50            # A — set to a safe BMS-derated value
MAX_DISCHARGE_CURRENT = 150        # A — set to a safe BMS-derated value

# ======================================================================
# JBD BLE PROTOCOL
# ======================================================================
FF01 = "0000ff01-0000-1000-8000-00805f9b34fb"   # notify (BMS → host)
FF02 = "0000ff02-0000-1000-8000-00805f9b34fb"   # write  (host → BMS)


def _build_auth_frame(cmd: int, data: bytes) -> bytes:
    """Build a JBD authentication frame (FF AA <cmd> <len> <data...> <checksum>).

    The checksum is the low byte of (cmd + len + sum(data)). Verified against
    known-good frames for pin "000000" (ff aa 15 06 30*6 3b) and the session
    init (ff aa 17 00 17).
    """
    length = len(data)
    checksum = (cmd + length + sum(data)) & 0xFF
    return bytes([0xFF, 0xAA, cmd, length]) + data + bytes([checksum])


def _validate_pin(pin: str) -> bytes:
    """Validate the BMS pin and return its ASCII bytes."""
    if not pin.isdigit() or len(pin) != 6:
        raise ValueError(
            f"BMS_PIN must be 6 decimal digits, got {pin!r}. "
            "Check the pin in your JBD/Xiaoxiang app (default = '000000')."
        )
    return pin.encode("ascii")


# Auth frames built once from BMS_PIN
HV_LOGIN = _build_auth_frame(0x15, _validate_pin(BMS_PIN))
HV_SESSION = _build_auth_frame(0x17, b"")

# Data-read commands (DD A5 ... 77 protocol, static)
CMD_BASIC = bytes.fromhex("dda50300fffd77")     # 0x03 = basic info
CMD_CELLS = bytes.fromhex("dda50400fffc77")     # 0x04 = cell voltages

# ======================================================================
# State
# ======================================================================
_buf = bytearray()
_done = asyncio.Event()


def _on_notify(_handle, data: bytearray) -> None:
    _buf.extend(data)
    if _buf and _buf[-1] == 0x77:
        _done.set()


async def _req(client: BleakClient, frame: bytes, timeout: float = NOTIFY_WAIT) -> bytes:
    _buf.clear()
    _done.clear()
    await client.write_gatt_char(FF02, frame, response=False)
    try:
        await asyncio.wait_for(_done.wait(), timeout)
    except asyncio.TimeoutError:
        pass
    return bytes(_buf)


# ======================================================================
# Parsers
# ======================================================================
def parse_basic(d: bytes) -> dict:
    if len(d) < 30 or d[:2] != b"\xdd\x03":
        raise ValueError(f"basic parse fail len={len(d)}")
    p = d[4:]
    voltage = int.from_bytes(p[0:2], "big") / 100.0
    current = int.from_bytes(p[2:4], "big", signed=True) / 100.0
    capacity_ah = int.from_bytes(p[4:6], "big") / 100.0
    capacity_full_ah = int.from_bytes(p[6:8], "big") / 100.0
    cycles = int.from_bytes(p[8:10], "big")
    soc = p[19]
    cells = p[21]
    ntc = p[22]
    temps: list[float] = []
    for i in range(ntc):
        off = 23 + 2 * i
        if off + 2 <= len(p):
            raw = int.from_bytes(p[off:off + 2], "big")
            temps.append((raw - 2731) / 10.0)
    return {
        "voltage": round(voltage, 2),
        "current": round(current, 2),
        "soc": int(soc),
        "capacity_ah": round(capacity_ah, 2),
        "capacity_full_ah": round(capacity_full_ah, 2),
        "cycles": int(cycles),
        "cell_count": int(cells),
        "temperature_count": int(ntc),
        "temperatures": temps,
    }


def parse_cells(d: bytes) -> dict:
    if len(d) < 6 or d[:2] != b"\xdd\x04":
        raise ValueError(f"cells parse fail len={len(d)}")
    n = d[3] // 2
    cells = []
    for i in range(n):
        off = 4 + 2 * i
        cells.append(int.from_bytes(d[off:off + 2], "big") / 1000.0)
    return {
        "cell_voltages": cells,
        "cell_min": round(min(cells), 3) if cells else None,
        "cell_max": round(max(cells), 3) if cells else None,
        "cell_delta_mv": round((max(cells) - min(cells)) * 1000, 0) if cells else None,
    }


# ======================================================================
# Payload — matches dbus-mqtt-battery JSON schema
# ======================================================================
def make_payload(d: dict) -> dict:
    v = d["voltage"]
    i = d["current"]
    soc = d["soc"]
    t = d["temperatures"][0] if d["temperatures"] else None
    capacity_remaining = round(INSTALLED_CAPACITY_AH * soc / 100.0, 2)
    return {
        "Dc": {
            "Power": round(v * i, 1),
            "Voltage": v,
            "Current": i,
            "Temperature": t,
        },
        "Soc": soc,
        "InstalledCapacity": INSTALLED_CAPACITY_AH,
        "Capacity": capacity_remaining,
        "ConsumedAmphours": round(INSTALLED_CAPACITY_AH - capacity_remaining, 2),
        "History": {
            "ChargeCycles": d["cycles"],
        },
        "System": {
            "NrOfCellsPerBattery": d["cell_count"],
            "MinCellVoltage": d.get("cell_min"),
            "MaxCellVoltage": d.get("cell_max"),
        },
        "Info": {
            "MaxChargeVoltage": MAX_CHARGE_VOLTAGE,
            "MaxChargeCurrent": MAX_CHARGE_CURRENT,
            "MaxDischargeCurrent": MAX_DISCHARGE_CURRENT,
        },
        "Balancing": 0,
        "SystemSwitch": 1,
    }


# ======================================================================
# MQTT
# ======================================================================
def mqtt_connect() -> mqtt.Client:
    # Compatible with paho-mqtt v1 and v2
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    else:
        client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    return client


# ======================================================================
# BMS read
# ======================================================================
async def read_bms_once() -> dict:
    async with BleakClient(BMS_MAC, timeout=BLE_TIMEOUT) as client:
        await client.start_notify(FF01, _on_notify)
        await _req(client, HV_LOGIN, 8)
        await _req(client, HV_SESSION, 8)
        basic = parse_basic(await _req(client, CMD_BASIC, NOTIFY_WAIT))
        cells = parse_cells(await _req(client, CMD_CELLS, NOTIFY_WAIT))
        await client.stop_notify(FF01)
        return {**basic, **cells}


# ======================================================================
# Main loop
# ======================================================================
async def main() -> None:
    print("JBD -> Victron Venus OS MQTT bridge")
    print(f"BMS  : {BMS_MAC}")
    print(f"MQTT : {MQTT_HOST}:{MQTT_PORT} topic={MQTT_TOPIC}")
    print(f"Poll : {POLL_INTERVAL}s")
    print("-" * 60)

    mq = mqtt_connect()
    fail_count = 0
    try:
        while True:
            try:
                data = await read_bms_once()
                payload = make_payload(data)
                mq.publish(MQTT_TOPIC, json.dumps(payload), qos=0, retain=True)
                temp_str = (
                    f"{data['temperatures'][0]:.1f}C"
                    if data["temperatures"]
                    else "n/a"
                )
                print(
                    f"[{time.strftime('%H:%M:%S')}] "
                    f"V={data['voltage']:.2f} "
                    f"I={data['current']:+.2f}A "
                    f"SOC={data['soc']}% "
                    f"T={temp_str} "
                    f"dV={data['cell_delta_mv']}mV -> publish OK"
                )
                fail_count = 0
            except (BleakError, asyncio.TimeoutError, ValueError) as e:
                fail_count += 1
                print(f"[{time.strftime('%H:%M:%S')}] BMS read fail #{fail_count}: {e}")
            except Exception as e:
                fail_count += 1
                print(f"[{time.strftime('%H:%M:%S')}] ERROR {type(e).__name__}: {e}")
            await asyncio.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        mq.loop_stop()
        mq.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
