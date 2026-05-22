#!/usr/bin/env bash
# install_linux.sh — One-shot installer for Ubuntu / Debian / Raspberry Pi OS.
#
# Installs system dependencies, creates a Python virtual environment in the
# repo directory, installs Python packages, and (optionally) installs a
# systemd service for auto-start at boot.
#
# Project : https://github.com/Ab0u/jbd_bms-victron-bridge
# License : MIT

set -euo pipefail

# --- Locate repo root (one level up from this script) -----------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# --- Pretty output ----------------------------------------------------------
GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; BOLD="\033[1m"; RESET="\033[0m"
say()  { printf "%b%s%b\n" "${GREEN}" "$*" "${RESET}"; }
warn() { printf "%b%s%b\n" "${YELLOW}" "$*" "${RESET}"; }
err()  { printf "%b%s%b\n" "${RED}"   "$*" "${RESET}" >&2; }

# --- Pre-flight checks ------------------------------------------------------
if [[ "${EUID}" -eq 0 ]]; then
  warn "Running as root. The virtual env and service will be owned by root."
  warn "For a normal install, run as your usual user (sudo will be used where needed)."
fi

if ! command -v apt >/dev/null 2>&1; then
  err "This installer expects Debian / Ubuntu / Raspberry Pi OS (apt not found)."
  err "On other distros, install python3, python3-pip, python3-venv, bluez, git manually."
  exit 1
fi

# --- System packages --------------------------------------------------------
say "==> Installing system packages..."
sudo apt update
sudo apt install -y \
  python3 \
  python3-pip \
  python3-venv \
  git \
  bluetooth \
  bluez

# --- Bluetooth service ------------------------------------------------------
say "==> Enabling Bluetooth service..."
sudo systemctl enable --now bluetooth
if ! systemctl is-active --quiet bluetooth; then
  err "Bluetooth service failed to start. Check 'systemctl status bluetooth'."
  exit 1
fi

# --- BLE adapter check ------------------------------------------------------
say "==> Checking for a BLE adapter..."
if command -v hciconfig >/dev/null 2>&1; then
  if hciconfig 2>/dev/null | grep -q '^hci'; then
    say "    BLE adapter detected."
  else
    warn "    No BLE adapter found (hciconfig sees nothing)."
    warn "    The publisher needs a working BLE radio on this host."
  fi
else
  warn "    'hciconfig' not installed — skipping adapter check."
fi

# --- Python virtual environment --------------------------------------------
VENV_DIR="${REPO_DIR}/.venv"
if [[ -d "${VENV_DIR}" ]]; then
  say "==> Re-using existing virtual environment at ${VENV_DIR}"
else
  say "==> Creating virtual environment at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

# --- Python dependencies ----------------------------------------------------
say "==> Installing Python dependencies..."
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install -r "${REPO_DIR}/requirements.txt"
deactivate

# --- Optional: systemd service ---------------------------------------------
SERVICE_TEMPLATE="${SCRIPT_DIR}/jbd-venus-bridge.service"
SERVICE_DEST="/etc/systemd/system/jbd-venus-bridge.service"

if [[ -f "${SERVICE_TEMPLATE}" ]]; then
  echo
  read -r -p "Install systemd service for auto-start at boot? [y/N] " ans
  if [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]]; then
    say "==> Installing systemd service..."
    SVC_USER="${SUDO_USER:-${USER}}"
    sudo sed \
      -e "s|@REPO_DIR@|${REPO_DIR}|g" \
      -e "s|@USER@|${SVC_USER}|g" \
      "${SERVICE_TEMPLATE}" \
      | sudo tee "${SERVICE_DEST}" >/dev/null
    sudo systemctl daemon-reload
    say "    Service installed at ${SERVICE_DEST}"
    say "    Enable & start:   sudo systemctl enable --now jbd-venus-bridge"
    say "    View status:      sudo systemctl status jbd-venus-bridge"
    say "    Tail the log:     journalctl -u jbd-venus-bridge -f"
  else
    say "    Skipping systemd service (you can install it later)."
  fi
fi

# --- Summary ----------------------------------------------------------------
echo
say "${BOLD}Installation complete.${RESET}"
echo
echo "Next steps:"
echo "  1. Find your BMS MAC:"
echo "       ${VENV_DIR}/bin/python ${REPO_DIR}/scripts/ble_scan.py"
echo
echo "  2. Edit ${REPO_DIR}/jbd_venus_mqtt.py and set:"
echo "       BMS_MAC, BMS_PIN, MQTT_HOST, MQTT_TOPIC, capacity / limits"
echo
echo "  3. Run the publisher:"
echo "       ${VENV_DIR}/bin/python ${REPO_DIR}/jbd_venus_mqtt.py"
