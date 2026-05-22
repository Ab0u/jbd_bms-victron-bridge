# Architecture

This document describes the data flow and components of
`jbd_bms-victron-bridge`.

## High-level diagram

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

## Components

### 1. JBD BMS

A JBD (Jiabaida) Smart BMS with a built-in BLE module. It exposes two GATT
characteristics under a vendor-specific service:

| UUID | Direction | Use |
|------|-----------|-----|
| `0000ff01-0000-1000-8000-00805f9b34fb` | BMS → host (notify) | Returns response frames |
| `0000ff02-0000-1000-8000-00805f9b34fb` | host → BMS (write w/o response) | Sends command frames |

### 2. Publisher (this script)

Implemented in `jbd_venus_mqtt.py`. The loop is:

1. Open BLE connection to the BMS MAC.
2. Subscribe to FF01 notifications.
3. Send the login + session-init handshake frames.
4. Request `0x03` (basic info) → parse voltage, current, SoC, cell count,
   NTC count, temperatures, cycles, capacity.
5. Request `0x04` (cell voltages) → parse per-cell voltages, compute
   min/max/delta.
6. Compose a JSON payload conforming to the `dbus-mqtt-battery` schema.
7. Publish the payload (QoS 0, retained) to the configured topic.
8. Disconnect and sleep `POLL_INTERVAL` seconds.

Disconnecting between reads is intentional: it keeps the BLE channel free
for occasional use from the JBD smartphone app, and it makes the script
resilient to BMS BLE deep-sleep cycles.

### 3. MQTT broker

Mosquitto, shipped with Venus OS, listening on TCP/1883 (plaintext) and
8883 (TLS). The driver subscribes locally on `127.0.0.1`; the publisher
connects from the LAN.

### 4. Driver `dbus-mqtt-battery`

Third-party driver by [@mr-manuel](https://github.com/mr-manuel/venus-os_dbus-mqtt-battery).
Once the JSON payload arrives, the driver registers a dbus service of type
`com.victronenergy.battery.mqtt_battery_<instance>` and maps the JSON fields
onto the standard Victron battery dbus paths:

| JSON key | dbus path |
|----------|-----------|
| `Dc.Voltage` | `/Dc/0/Voltage` |
| `Dc.Current` | `/Dc/0/Current` |
| `Dc.Power` | `/Dc/0/Power` |
| `Dc.Temperature` | `/Dc/0/Temperature` |
| `Soc` | `/Soc` |
| `InstalledCapacity` | `/InstalledCapacity` |
| `Capacity` | `/Capacity` |
| `ConsumedAmphours` | `/ConsumedAmphours` |
| `Info.MaxChargeVoltage` | `/Info/MaxChargeVoltage` |
| `Info.MaxChargeCurrent` | `/Info/MaxChargeCurrent` |
| `Info.MaxDischargeCurrent` | `/Info/MaxDischargeCurrent` |

The GX UI and VRM read directly from dbus, so once the service is
registered the battery is visible everywhere it would be if it were a
native Victron product.

## JSON payload example

```json
{
  "Dc": {
    "Power": 547.4,
    "Voltage": 13.57,
    "Current": 40.34,
    "Temperature": 21.8
  },
  "Soc": 79,
  "InstalledCapacity": 280.0,
  "Capacity": 221.2,
  "ConsumedAmphours": 58.8,
  "History": { "ChargeCycles": 46 },
  "System": {
    "NrOfCellsPerBattery": 4,
    "MinCellVoltage": 3.370,
    "MaxCellVoltage": 3.374
  },
  "Info": {
    "MaxChargeVoltage": 14.0,
    "MaxChargeCurrent": 50,
    "MaxDischargeCurrent": 150
  },
  "Balancing": 0,
  "SystemSwitch": 1
}
```

## Timing

| Event | Typical interval | Configurable via |
|-------|------------------|------------------|
| BMS read & publish | 5 s | `POLL_INTERVAL` |
| Driver "no data" timeout | 60 s | `timeout` in `config.ini` |
| Driver auto-restart on timeout | immediate | daemontools `svscan` |

If the publisher dies, the driver detects the silence after `timeout`
seconds and exits; `svscan` immediately restarts it, and it then waits for
new data. The battery tile in the GX UI disappears within a minute of the
publisher going offline.
