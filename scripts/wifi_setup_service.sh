#!/bin/bash
# Runs as the nuggies-wifi-setup systemd service (as root).
# If the Pi has no WiFi on boot, starts the NuggiesSetup hotspot and
# a captive portal so the user can configure WiFi from a browser.

set -euo pipefail

PROJECT_DIR="/home/pi/nuggies_pi_displays"
LOG="$PROJECT_DIR/logs/wifi_setup.log"
NM_DNSMASQ_DIR="/etc/NetworkManager/dnsmasq-shared.d"
AP_IP="10.42.0.1"

mkdir -p "$PROJECT_DIR/logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Nuggies WiFi boot check starting ==="

# Give NetworkManager time to attempt saved connections before we judge.
sleep 8

CONNECTIVITY=$(nmcli -t -f CONNECTIVITY general 2>/dev/null || echo "unknown")
log "NM connectivity: $CONNECTIVITY"

if [[ "$CONNECTIVITY" == "full" || "$CONNECTIVITY" == "limited" ]]; then
    log "WiFi connected — no setup needed."
    exit 0
fi

log "No WiFi connection detected. Starting captive portal setup..."

# --- Remove the 80 → 8000 iptables forward so port 80 reaches us directly ---
iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null || true
log "Removed port-80 forward rule (if present)."

# --- Install dnsmasq config so NM redirects all DNS to us ---
mkdir -p "$NM_DNSMASQ_DIR"
cp "$PROJECT_DIR/wifi_setup/ap_config/captive-portal.conf" \
   "$NM_DNSMASQ_DIR/captive-portal.conf"
log "Installed captive-portal dnsmasq config."

# --- Start the open hotspot ---
log "Starting NuggiesSetup hotspot..."
nmcli device wifi hotspot \
    ifname wlan0 \
    ssid "NuggiesSetup" \
    con-name "NuggiesHotspot" 2>&1 | tee -a "$LOG" || {
    log "ERROR: Failed to start hotspot. Is NetworkManager running?"
    exit 1
}

# Wait for the AP IP to be assigned before starting the portal.
for i in $(seq 1 10); do
    AP_ADDR=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet )\d+\.\d+\.\d+\.\d+' || true)
    if [[ -n "$AP_ADDR" ]]; then
        log "Hotspot up — AP address: $AP_ADDR"
        break
    fi
    sleep 1
done

log "Starting captive portal on port 80..."
# exec replaces this script with uvicorn — systemd then tracks uvicorn directly.
exec python3 -m uvicorn wifi_setup.captive_portal:app \
    --host 0.0.0.0 \
    --port 80 \
    --log-level warning \
    --no-access-log
