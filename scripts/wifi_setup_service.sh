#!/bin/bash
# Runs as the nuggies-wifi-setup systemd service (as root).
# If the Pi has no WiFi on boot, starts the NuggiesSetup hotspot and
# a captive portal so the user can configure WiFi from a browser.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$PROJECT_DIR/logs/wifi_setup.log"
NM_DNSMASQ_DIR="/etc/NetworkManager/dnsmasq-shared.d"

_AP_CFG="$PROJECT_DIR/wifi_ap.yaml"
AP_SSID=$(grep '^ssid:'            "$_AP_CFG" | sed 's/^ssid:[[:space:]]*//')
AP_PASSWORD=$(grep '^password:'    "$_AP_CFG" | sed 's/^password:[[:space:]]*//')
AP_CON_NAME=$(grep '^connection_name:' "$_AP_CFG" | sed 's/^connection_name:[[:space:]]*//')
AP_IP=$(grep '^ap_ip:'            "$_AP_CFG" | sed 's/^ap_ip:[[:space:]]*//')

mkdir -p "$PROJECT_DIR/logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Nuggies WiFi boot check starting ==="

SKIP_WIFI_CHECK=false

# If a factory WiFi reset was requested, wipe all saved WiFi connections now
# (running as root, so nmcli has the permissions the API user lacks).
if [[ -f "$PROJECT_DIR/.factory_wifi_reset" ]]; then
    log "Factory WiFi reset marker found — wiping all saved WiFi connections..."
    while IFS=: read -r uuid type; do
        [[ "$type" == "802-11-wireless" ]] || continue
        nmcli connection delete "$uuid" 2>/dev/null \
            && log "  Deleted connection: $uuid" || true
    done < <(nmcli -t -f UUID,TYPE connection show 2>/dev/null || true)
    nmcli device disconnect wlan0 2>/dev/null || true
    rm -f "$PROJECT_DIR/.factory_wifi_reset"
    log "WiFi connections wiped — skipping connectivity check."
    SKIP_WIFI_CHECK=true
fi

# If a force-portal flag was written (e.g. by factory-reset-wifi endpoint), skip the
# WiFi connectivity check entirely and go straight to captive portal setup.
if [[ -f "$PROJECT_DIR/.force_portal" ]]; then
    rm -f "$PROJECT_DIR/.force_portal"
    log "Force-portal flag found — skipping WiFi check, starting captive portal directly."
elif [[ "$SKIP_WIFI_CHECK" == "true" ]]; then
    log "Starting captive portal after WiFi wipe."
else
    # Give NetworkManager time to attempt saved connections before we judge.
    sleep 8

    CONNECTIVITY=$(nmcli -t -f CONNECTIVITY general 2>/dev/null || echo "unknown")
    log "NM connectivity: $CONNECTIVITY"

    # Check wlan0 specifically — ethernet alone should still trigger the portal
    WLAN_STATE=$(nmcli -t -f DEVICE,STATE device status 2>/dev/null | grep "^wlan0:" | cut -d: -f2 || echo "unknown")
    log "wlan0 state: $WLAN_STATE"

    ACTIVE_CON=$(nmcli -t -f DEVICE,CONNECTION device status 2>/dev/null | grep "^wlan0:" | cut -d: -f2 || echo "")
    if [[ "$WLAN_STATE" == "connected" && "$ACTIVE_CON" != "$AP_CON_NAME" ]]; then
        log "WiFi connected as client ($ACTIVE_CON) — no setup needed."
        iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null || true
        log "Port-80 → 8000 redirect ensured."
        exit 0
    fi
fi

log "No WiFi connection detected. Starting captive portal setup..."

# --- Remove the 80 → 8000 iptables forward so port 80 reaches us directly ---
iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null || true
log "Removed port-80 forward rule (if present)."

# --- Remove any stale captive-portal dnsmasq config before hotspot starts ---
# (Installing it before NM starts the shared connection can cause dnsmasq to fail)
rm -f "$NM_DNSMASQ_DIR/captive-portal.conf"
log "Cleared stale captive-portal dnsmasq config (if any)."

# --- Stop system dnsmasq so NM's hotspot dnsmasq can bind to port 53 ---
systemctl stop dnsmasq 2>/dev/null && log "Stopped system dnsmasq." || log "System dnsmasq not running (OK)."

# --- Clean up any stale hotspot connection and release the interface ---
nmcli connection delete "$AP_CON_NAME" 2>/dev/null && log "Removed stale $AP_CON_NAME connection." || true
nmcli device disconnect wlan0 2>/dev/null || true
sleep 2
log "Interface released, starting hotspot..."

# --- Start the open hotspot ---
log "Starting NuggiesSetup hotspot..."
nmcli device wifi hotspot \
    ifname wlan0 \
    ssid "$AP_SSID" \
    con-name "$AP_CON_NAME" \
    password "$AP_PASSWORD" \
    band bg 2>&1 | tee -a "$LOG" || {
    log "ERROR: Failed to start hotspot. Is NetworkManager running?"
    exit 1
}

# Wait for the AP IP to be assigned before continuing.
AP_ADDR=""
for i in $(seq 1 15); do
    AP_ADDR=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet )\d+\.\d+\.\d+\.\d+' || true)
    if [[ -n "$AP_ADDR" ]]; then
        log "Hotspot up — AP address: $AP_ADDR"
        break
    fi
    sleep 1
done

if [[ -z "$AP_ADDR" ]]; then
    log "WARNING: AP address not detected after 15s, using default $AP_IP"
    AP_ADDR="$AP_IP"
fi

# --- Install dnsmasq config NOW that the hotspot is up ---
mkdir -p "$NM_DNSMASQ_DIR"
cp "$PROJECT_DIR/wifi_setup/ap_config/captive-portal.conf" \
   "$NM_DNSMASQ_DIR/captive-portal.conf"
log "Installed captive-portal dnsmasq config."

# Signal NM's dnsmasq to reload the new config
pkill -HUP -f "dnsmasq" 2>/dev/null && log "Reloaded dnsmasq." || log "dnsmasq not running yet (OK)."

log "Starting setup display on matrix..."
python3 "$PROJECT_DIR/display/setup/main.py" >> "$LOG" 2>&1 &
DISPLAY_PID=$!
log "Setup display started (pid $DISPLAY_PID)."

log "Starting captive portal on port 80..."
# exec replaces this script with uvicorn — systemd then tracks uvicorn directly.
# The setup display process will be orphaned when uvicorn takes over; systemd
# will clean it up when the service stops.
exec python3 -m uvicorn wifi_setup.captive_portal:app \
    --host 0.0.0.0 \
    --port 80 \
    --log-level warning \
    --no-access-log
