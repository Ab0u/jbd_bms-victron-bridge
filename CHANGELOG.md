# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-05-22

### Added
- `install/install_linux.sh` — convenience installer for Ubuntu / Debian /
  Raspberry Pi OS: apt deps, Python venv, pip install, optional systemd
  service registration.
- `install/install_windows.ps1` — PowerShell installer that detects Python,
  installs pip dependencies, checks the Bluetooth adapter, and optionally
  registers a Task Scheduler entry for auto-start.
- `install/jbd-venus-bridge.service` — systemd unit template with hardening
  options.
- `install/README.md` — usage of the convenience installers.

### Changed
- Main README Quick start now points to the convenience installers.
- Repository layout section updated.

## [1.1.0] — 2026-05-22

### Added
- Configurable `BMS_PIN` setting. Users with a non-default JBD pin no longer
  have to hand-craft the login frame.
- Dynamic authentication frame builder with checksum calculation
  (`(cmd + len + sum(data)) & 0xFF`).
- Pin validation: rejects anything other than a 6-digit numeric string with
  a clear error message.
- Troubleshooting entry for connect-but-no-data symptoms caused by a wrong
  pin.

### Changed
- `HV_LOGIN` / `HV_SESSION` are now built at startup from `BMS_PIN` instead
  of being hard-coded hex strings.

## [1.0.0] — 2026-05-20

### Added
- Initial public release.
- BLE reader for JBD / Xiaoxiang BMS (FF01 notify / FF02 write).
- Parsers for basic info (voltage, current, SoC, cycles, temperatures) and
  cell voltages.
- MQTT publisher compatible with the `dbus-mqtt-battery` Venus OS driver
  JSON schema.
- `ble_scan.py` diagnostic tool for discovering the BMS MAC address.
- Documentation: README, architecture, troubleshooting.
- Tested end-to-end with a JBD 4S 100A BMS, 4× LF280K LFP cells, and
  Venus OS v3.34 on Raspberry Pi.
