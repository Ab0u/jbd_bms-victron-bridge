#!/usr/bin/env python3
"""
ble_scan.py — Diagnostic Bluetooth LE scanner.

Lists all BLE devices visible from this host along with their advertised name
and RSSI. Use it to confirm that the JBD BMS is broadcasting and to read its
MAC address before configuring jbd_venus_mqtt.py.

Project : https://github.com/Ab0u/jbd_bms-victron-bridge
Author  : M. Hajji (@Ab0u)
License : MIT
"""
import asyncio
import sys

from bleak import BleakScanner


SCAN_DURATION = 15.0  # seconds


async def main() -> None:
    print(f"Scanning {SCAN_DURATION:.0f}s...")
    devices = await BleakScanner.discover(timeout=SCAN_DURATION, return_adv=True)

    if not devices:
        print("No BLE devices found.")
        print("- Check that Bluetooth is enabled on this host.")
        print("- On Linux: 'systemctl status bluetooth'")
        sys.exit(1)

    rows = []
    for addr, (dev, adv) in devices.items():
        rows.append((addr, dev.name or "?", adv.rssi))

    # Sort by RSSI descending (strongest signal first)
    rows.sort(key=lambda r: r[2], reverse=True)

    width = max(len(r[1]) for r in rows)
    for addr, name, rssi in rows:
        print(f"{addr}  {name:<{width}}  RSSI={rssi}")

    print(f"\nTotal: {len(rows)} device(s).")
    print("\nLook for an entry that matches your JBD BMS (often named")
    print("'xiaoxiang BMS', 'JBD-...' or a custom name set in the JBD app).")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
