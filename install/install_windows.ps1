<#
.SYNOPSIS
    One-shot installer for jbd_bms-victron-bridge on Windows.

.DESCRIPTION
    - Verifies Python 3.8+ is available
    - Installs Python dependencies (bleak, paho-mqtt)
    - Optionally registers a Task Scheduler entry for auto-start at boot

.PARAMETER InstallScheduledTask
    If supplied, prompts to register a scheduled task that runs the
    publisher on user login (no admin rights required).

.EXAMPLE
    PS> .\install\install_windows.ps1

.EXAMPLE
    PS> .\install\install_windows.ps1 -InstallScheduledTask

.NOTES
    Project : https://github.com/Ab0u/jbd_bms-victron-bridge
    License : MIT
#>

[CmdletBinding()]
param(
    [switch]$InstallScheduledTask
)

$ErrorActionPreference = 'Stop'

function Write-Step    { param($Msg) Write-Host "==> $Msg" -ForegroundColor Green }
function Write-Warn    { param($Msg) Write-Host "    $Msg" -ForegroundColor Yellow }
function Write-Err     { param($Msg) Write-Host "    $Msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Locate the repo root (one level up from this script)
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir   = (Resolve-Path (Join-Path $ScriptDir '..')).Path

Write-Step "jbd_bms-victron-bridge — Windows installer"
Write-Host "    Repo directory: $RepoDir"
Write-Host ""

# ---------------------------------------------------------------------------
# Check Python
# ---------------------------------------------------------------------------
Write-Step "Checking for Python 3.8+"
$python = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $ver = & $candidate -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null
            if ($ver -match '^3\.(8|9|1\d)') {
                $python = $candidate
                Write-Host "    Found: $candidate ($ver)"
                break
            }
        } catch { }
    }
}

if (-not $python) {
    Write-Err "Python 3.8+ is not installed or not on PATH."
    Write-Err "Download from https://www.python.org/downloads/ and re-run."
    Write-Err "During install, tick 'Add Python to PATH'."
    exit 1
}

# ---------------------------------------------------------------------------
# Install Python packages
# ---------------------------------------------------------------------------
Write-Step "Installing Python dependencies"
$reqFile = Join-Path $RepoDir 'requirements.txt'
& $python -m pip install --upgrade pip
& $python -m pip install --user -r $reqFile

# ---------------------------------------------------------------------------
# Bluetooth check (informational)
# ---------------------------------------------------------------------------
Write-Step "Checking for a Bluetooth adapter"
try {
    $bt = Get-PnpDevice -Class Bluetooth -ErrorAction Stop |
          Where-Object { $_.Status -eq 'OK' } |
          Select-Object -First 1
    if ($bt) {
        Write-Host "    Adapter detected: $($bt.FriendlyName)"
    } else {
        Write-Warn "No active Bluetooth adapter detected — BLE scan will fail."
    }
} catch {
    Write-Warn "Could not query Bluetooth devices: $($_.Exception.Message)"
}

# ---------------------------------------------------------------------------
# Optional: Task Scheduler entry
# ---------------------------------------------------------------------------
if ($InstallScheduledTask) {
    Write-Step "Registering Task Scheduler entry"
    $taskName  = "JBD Venus Bridge"
    $script    = Join-Path $RepoDir 'jbd_venus_mqtt.py'
    $pythonw   = (Get-Command pythonw -ErrorAction SilentlyContinue)?.Source
    if (-not $pythonw) {
        # Fall back to python (will show a console window)
        $pythonw = (Get-Command $python).Source
    }

    $action    = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`""
    $trigger   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings  = New-ScheduledTaskSettingsSet `
                    -StartWhenAvailable `
                    -RestartCount 999 `
                    -RestartInterval (New-TimeSpan -Minutes 1) `
                    -DontStopOnIdleEnd

    try {
        Register-ScheduledTask -TaskName $taskName `
                               -Action $action `
                               -Trigger $trigger `
                               -Settings $settings `
                               -Description "Bridge JBD BMS BLE data to Venus OS MQTT" `
                               -Force | Out-Null
        Write-Host "    Task '$taskName' registered (runs at login)."
        Write-Host "    To start now:  Start-ScheduledTask -TaskName '$taskName'"
        Write-Host "    To remove:     Unregister-ScheduledTask -TaskName '$taskName'"
    } catch {
        Write-Err "Failed to register task: $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Step "Installation complete."
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Find your BMS MAC:"
Write-Host "       $python `"$(Join-Path $RepoDir 'scripts\ble_scan.py')`""
Write-Host ""
Write-Host "  2. Open jbd_venus_mqtt.py and set:"
Write-Host "       BMS_MAC, BMS_PIN, MQTT_HOST, MQTT_TOPIC, capacity / limits"
Write-Host ""
Write-Host "  3. Run the publisher:"
Write-Host "       $python `"$(Join-Path $RepoDir 'jbd_venus_mqtt.py')`""
