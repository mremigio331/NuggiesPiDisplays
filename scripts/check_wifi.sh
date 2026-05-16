#!/bin/bash
# Manual trigger: checks whether wlan0 has a client WiFi connection and
# starts the captive portal service if not. Run this when you want to
# trigger the setup portal without rebooting.
#
# Boot-time WiFi checking is handled by nuggies-wifi-setup.service (systemd).
# Do NOT add this script to cron — that would double-fire the same check.

PROJECT_DIR="/home/pi/nuggies_pi_displays"
LOG="$PROJECT_DIR/logs/check_wifi.log"

_AP_CFG="$PROJECT_DIR/wifi_ap.yaml"
AP_CON_NAME=$(grep '^connection_name:' "$_AP_CFG" | sed 's/^connection_name:[[:space:]]*//')

mkdir -p "$PROJECT_DIR/logs"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== WiFi check ==="

# Give NetworkManager time to attempt saved connections on boot.
sleep 10

WLAN_STATE=$(nmcli -t -f DEVICE,STATE device status 2>/dev/null \
    | grep "^wlan0:" | cut -d: -f2 || echo "unknown")
ACTIVE_CON=$(nmcli -t -f DEVICE,CONNECTION device status 2>/dev/null \
    | grep "^wlan0:" | cut -d: -f2 || echo "")

log "wlan0 state: $WLAN_STATE  active connection: ${ACTIVE_CON:-none}"

if [[ "$WLAN_STATE" == "connected" && "$ACTIVE_CON" != "$AP_CON_NAME" ]]; then
    log "WiFi connected as client — nothing to do."
    exit 0
fi

if [[ "$ACTIVE_CON" == "$AP_CON_NAME" ]]; then
    log "Already in hotspot/captive-portal mode — nothing to do."
    exit 0
fi

log "No WiFi connection found — starting nuggies-wifi-setup service..."
systemctl start nuggies-wifi-setup.service
log "nuggies-wifi-setup service started."
