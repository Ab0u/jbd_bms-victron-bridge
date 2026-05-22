# Installers

Convenience scripts that wrap the manual install steps from the main README.

| File | Platform | Purpose |
|------|----------|---------|
| `install_linux.sh` | Ubuntu / Debian / RPi OS | apt deps + venv + pip install + optional systemd service |
| `install_windows.ps1` | Windows 10 / 11 | pip install + optional Task Scheduler entry |
| `jbd-venus-bridge.service` | systemd | Template substituted by `install_linux.sh` |

## Linux (Ubuntu / Debian / Raspberry Pi OS)

```bash
git clone https://github.com/Ab0u/jbd_bms-victron-bridge.git
cd jbd_bms-victron-bridge
bash install/install_linux.sh
```

The script:

1. Installs `python3`, `python3-pip`, `python3-venv`, `git`, `bluetooth`,
   `bluez` via `apt`.
2. Enables and starts the Bluetooth service.
3. Verifies a BLE adapter is present.
4. Creates `.venv/` in the repo directory and installs Python dependencies.
5. Optionally installs `/etc/systemd/system/jbd-venus-bridge.service` for
   auto-start at boot (you are asked interactively).

If you accept the systemd step, enable & start the service with:

```bash
sudo systemctl enable --now jbd-venus-bridge
journalctl -u jbd-venus-bridge -f
```

## Windows 10 / 11

In PowerShell:

```powershell
git clone https://github.com/Ab0u/jbd_bms-victron-bridge.git
cd jbd_bms-victron-bridge
.\install\install_windows.ps1
```

To also register a Task Scheduler entry that starts the publisher at user
login, add `-InstallScheduledTask`:

```powershell
.\install\install_windows.ps1 -InstallScheduledTask
```

If PowerShell blocks the script with an execution policy error, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

The script:

1. Detects a working Python 3.8+ interpreter (tries `python`, `python3`,
   `py`).
2. Runs `pip install --user -r requirements.txt`.
3. Checks for a Bluetooth adapter.
4. (Optional) Registers a Task Scheduler job named "JBD Venus Bridge" that
   runs `pythonw jbd_venus_mqtt.py` at user login with auto-restart on
   failure.

## Venus OS

The Venus driver (`dbus-mqtt-battery` by mr-manuel) is installed manually
as documented in the main README, section *Installation — Venus OS
(driver)*. There is no convenience script for it because Venus has a
non-standard userland (BusyBox + daemontools) where a generic shell
installer would not be portable.
