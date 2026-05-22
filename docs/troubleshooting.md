# Troubleshooting

Common problems and how to resolve them.

## BLE / publisher side

### `bleak.exc.BleakError: Device with address … was not found`

The BMS is not advertising on BLE. Causes:

1. **Out of range.** Move the publisher closer. RSSI above (i.e. closer to
   zero than) −85 is workable; below that the connection is unreliable.
2. **BMS in deep sleep.** JBD BMSes power down their BLE radio after a
   period of inactivity. To wake it: open the JBD / Xiaoxiang app on a
   phone and let it connect once, or apply a brief load to the pack.
3. **Another client is connected.** BLE peripherals accept one central at a
   time. Close the JBD app, then retry.

Verify visibility with:

```bash
python scripts/ble_scan.py
```

### `BleakDBusError: org.bluez.Error.NotReady`

Bluetooth is disabled or unauthorized on Linux. Fix:

```bash
sudo systemctl enable --now bluetooth
sudo usermod -aG bluetooth $USER     # then log out & back in
```

### `RuntimeError: This event loop is already running`

You ran the script inside an interactive Jupyter/IPython kernel.
Run it as a normal Python script.

### Publisher prints "publish OK" but driver still times out

Topic mismatch. Confirm:

```bash
grep topic /data/etc/dbus-mqtt-battery/config.ini
grep MQTT_TOPIC jbd_venus_mqtt.py
```

Both must be identical, e.g. `battery/jbd_jbd1`.

### BMS connects but immediately disconnects, or commands time out

Likely the wrong `BMS_PIN`. The BMS accepts the BLE connection but refuses
to honour data commands until it has received a valid authentication frame.
Symptoms: BLE connect succeeds, login frame is sent, but `parse_basic` /
`parse_cells` time out with empty buffers.

Open the JBD / Xiaoxiang app and confirm the pin. If you've forgotten it,
"Restore Manufacturer Settings" in the app resets it to `000000`.

## MQTT / Venus side

### `netstat -ln | grep 1883` shows nothing

Mosquitto did not start, or is bound only to localhost. Restart:

```bash
svc -t /service/mosquitto
```

If Mosquitto truly listens only on `127.0.0.1`, add a LAN listener by
creating `/data/conf/mosquitto.d/lan.conf`:

```
listener 1883 0.0.0.0
allow_anonymous true
```

Then restart Mosquitto.

### Driver log keeps showing `Waiting since 60 seconds…`

The driver is correctly subscribed but no MQTT message has arrived in time.
Check, from the Venus shell:

```bash
# Live subscribe to confirm messages flow
python3 - <<'EOF'
import paho.mqtt.client as mqtt
def on_msg(c, u, m): print(m.topic, m.payload[:80])
c = mqtt.Client()
c.on_message = on_msg
c.connect('127.0.0.1', 1883, 60)
c.subscribe('battery/#')
c.loop_forever()
EOF
```

You should see one message every `POLL_INTERVAL` seconds.

### `python: can't open file '/data/etc/dbus-mqtt-battery/dbus-mqtt-battery.py'`

The driver directory is in the wrong place. The GitHub zip puts everything
under `venus-os_dbus-mqtt-battery-master/dbus-mqtt-battery/`. You must
**move** the inner folder to `/data/etc/dbus-mqtt-battery/` because
`service/run` hard-codes that path:

```bash
cd /data/etc
mv venus-os_dbus-mqtt-battery-master/dbus-mqtt-battery ./dbus-mqtt-battery
```

After moving, re-run `bash install.sh`.

## dbus / GX side

### `dbus.exceptions.DBusException: … no such name`

The driver process is crash-looping. Check:

```bash
svstat /service/dbus-mqtt-battery
tail -n 40 /var/log/dbus-mqtt-battery/current
```

A short uptime (< 5 s) with a Python traceback means a parse error or
missing module. Read the traceback.

### Service has the suffix `_100`

Normal — `dbus-mqtt-battery` appends the configured `device_instance`. The
full service name is, for instance,
`com.victronenergy.battery.mqtt_battery_100`. Use that when querying with
`dbus -y`.

### Battery shows but SoC is stuck

The publisher process is alive but blocked on something. Check its console
output: long pauses with no `publish OK` line means it is retrying BLE.
Restart the publisher.

### Warnings about `/raw/...` keys in the driver log

Cosmetic. The publisher includes extra debug keys (`raw`, `timestamp`)
that the driver does not know about. They do not affect the battery service.
Future versions of this script may strip them.

## VRM portal

### Battery not visible in VRM

VRM only pulls data when the bridge from the GX to `mqtt52.victronenergy.com`
is up. Confirm in **Settings → VRM online portal**.

VRM also has a small delay — give it 5–15 minutes after the first dbus
service appears.
