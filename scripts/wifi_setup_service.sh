#!/bin/bash
# Runs as the nuggies-wifi-setup systemd service (as root).
# If the Pi has no WiFi on boot, starts the NuggiesSetup hotspot and
# a captive portal so the user can configure WiFi from a browser.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="/var/log/nuggies/wifi_setup.log"
NM_DNSMASQ_DIR="/etc/NetworkManager/dnsmasq-shared.d"

_AP_CFG="$PROJECT_DIR/wifi_ap.yaml"
# Derive the visible setup-AP SSID from the hostname — never hardcoded — using the SAME
# rule as wifi_setup/ap_config.py: uppercase the first character, keep the rest unchanged,
# then append "Display" (stonks -> StonksDisplay). The Python derivation in ap_config.AP_SSID
# is what actually names the AP (python3 -m wifi_setup.wifi_manager --start-hotspot); this
# bash value is used only for logging and the stale-connection cleanup message, so we derive
# it identically to keep logs in agreement. Guard every step so it can never fail under
# `set -euo pipefail`: an empty hostname falls back to the yaml ssid, then literal NuggiesDisplay.
_HOSTNAME=$(hostname 2>/dev/null || true)
if [[ -n "$_HOSTNAME" ]]; then
    _SSID_FIRST=$(printf '%s' "$_HOSTNAME" | cut -c1 | tr '[:lower:]' '[:upper:]')
    _SSID_REST=$(printf '%s' "$_HOSTNAME" | cut -c2-)
    AP_SSID="${_SSID_FIRST}${_SSID_REST}Display"
else
    AP_SSID=$(grep '^ssid:' "$_AP_CFG" | sed 's/^ssid:[[:space:]]*//' || true)
    [[ -n "$AP_SSID" ]] || AP_SSID="NuggiesDisplay"
fi
AP_PASSWORD=$(grep '^password:'    "$_AP_CFG" | sed 's/^password:[[:space:]]*//')
AP_CON_NAME=$(grep '^connection_name:' "$_AP_CFG" | sed 's/^connection_name:[[:space:]]*//')
AP_IP=$(grep '^ap_ip:'            "$_AP_CFG" | sed 's/^ap_ip:[[:space:]]*//')

mkdir -p "$PROJECT_DIR/logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# Ensure exactly one port-80 → 8000 REDIRECT rule exists (client/connected mode).
# Check-then-add: -C returns non-zero when the rule is absent, which is expected and
# must not abort the script under `set -e`; the `||` handles that non-match cleanly by
# adding the rule. If the rule already exists, -C succeeds and we add nothing, so the
# rule count stays at exactly 1 no matter how many times this runs.
ensure_port80_redirect() {
    iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null \
        || iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000
    log "Port-80 → 8000 redirect ensured."
}

# Remove every port-80 → 8000 REDIRECT rule (portal mode owns port 80 directly).
# Loop while -C still matches so duplicate rules manufactured earlier all get cleared,
# leaving zero instances. Bounded by a max-iteration guard so a persistently-failing
# delete cannot spin forever. The -C check returning non-zero (no more matches) is the
# normal loop-exit condition and must not trip `set -e`, so it drives the `while` guard.
clear_port80_redirect() {
    local max_iter=10
    local i=0
    while iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null; do
        iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null || true
        i=$((i + 1))
        if [[ "$i" -ge "$max_iter" ]]; then
            log "WARNING: port-80 redirect delete hit max iterations ($max_iter) — giving up."
            break
        fi
    done
    log "Removed port-80 forward rule (if present)."
}

log "=== Nuggies WiFi boot check starting ==="

# If a factory WiFi reset was requested, wipe all saved WiFi connections now
# (running as root, so nmcli has the permissions the API user lacks). This privileged
# WIPE must happen BEFORE the verdict — the shared resolver knows the MEANING of the
# reset marker but does not do the profile deletion, which needs root. Removing
# .factory_wifi_reset here leaves the device with no saved networks, so the resolver's
# settle poll below returns unconfigured/no_association and we fall through to the portal.
if [[ -f "$PROJECT_DIR/.factory_wifi_reset" ]]; then
    log "Factory WiFi reset marker found — wiping all saved WiFi connections..."
    while IFS=: read -r uuid type; do
        [[ "$type" == "802-11-wireless" ]] || continue
        nmcli connection delete "$uuid" 2>/dev/null \
            && log "  Deleted connection: $uuid" || true
    done < <(nmcli -t -f UUID,TYPE connection show 2>/dev/null || true)
    nmcli device disconnect wlan0 2>/dev/null || true
    rm -f "$PROJECT_DIR/.factory_wifi_reset"
    log "WiFi connections wiped."
fi

# --- Resolve the configured verdict via the single shared resolver (task 2.1). ---
# One call replaces the old fixed `sleep 8` + point-in-time nmcli read AND the inline
# .force_portal handling: the resolver runs a bounded settle-poll (SETTLE_TIMEOUT_S=45)
# so "still associating" is never mistaken for "unconfigured", and it already consumes
# the MEANING of .force_portal (-> unconfigured/forced). It does NOT remove .force_portal
# itself, so the script removes that marker below AFTER the resolver has seen it.
# Output is one line: "<verdict> <reason> [ssid]", verdict ∈ {configured, unconfigured}.
VERDICT_LINE=$(cd "$PROJECT_DIR" && python3 -m wifi_setup.wifi_state --verdict 2>>"$LOG" || echo "unconfigured resolver_error")
log "WiFi verdict: $VERDICT_LINE"
VERDICT=$(awk '{print $1}' <<<"$VERDICT_LINE")

if [[ "$VERDICT" == "configured" ]]; then
    log "WiFi connected as client — no setup needed (verdict: $VERDICT_LINE)."
    ensure_port80_redirect
    exit 0
fi

# Unconfigured: consume the force-portal marker now that the resolver has already taken
# its meaning into account, then proceed to captive-portal setup.
if [[ -f "$PROJECT_DIR/.force_portal" ]]; then
    rm -f "$PROJECT_DIR/.force_portal"
    log "Force-portal flag consumed."
fi

log "No WiFi connection detected. Starting captive portal setup..."

# --- Remove the 80 → 8000 iptables forward so port 80 reaches us directly ---
clear_port80_redirect

# --- Stop system dnsmasq so NM's hotspot dnsmasq can bind to port 53 ---
systemctl stop dnsmasq 2>/dev/null && log "Stopped system dnsmasq." || log "System dnsmasq not running (OK)."

# --- Pre-install the catch-all dnsmasq config BEFORE the hotspot starts ---
# iOS probes for a captive portal the instant it connects. If the DNS catch-all
# isn't in place at that moment, iOS gets a DNS failure and decides there's no
# portal — and won't show the popup. Installing before NM starts its dnsmasq
# instance means the catch-all is active from the very first connection.
mkdir -p "$NM_DNSMASQ_DIR"
cp "$PROJECT_DIR/wifi_setup/ap_config/captive-portal.conf" \
   "$NM_DNSMASQ_DIR/captive-portal.conf"
log "Pre-installed captive-portal dnsmasq config."

# --- Clean up any stale hotspot connection and release the interface ---
nmcli connection delete "$AP_CON_NAME" 2>/dev/null && log "Removed stale $AP_CON_NAME connection." || true
nmcli device disconnect wlan0 2>/dev/null || true
sleep 2
log "Interface released."

# --- Cache a network scan while wlan0 is still free (before the AP takes the radio) ---
# The portal serves this cache when a live rescan is unavailable in AP mode. Runs as root
# here; the Python helper chowns the cache file back to the project-root owner so the pi
# API can read it. Non-fatal: a failed scan must not block portal bring-up.
log "Scanning networks to cache before hotspot..."
( cd "$PROJECT_DIR" && python3 -m wifi_setup.wifi_manager --scan-cache ) 2>&1 | tee -a "$LOG" \
    || log "WARNING: network scan cache failed (portal will fall back to a live rescan)."

log "Starting hotspot..."

# --- Start the WPA-protected hotspot ---
# Delegate to the single Python implementation so there is one hotspot invocation for
# every caller (SSID/password/con-name/band all come from wifi_ap.yaml via ap_config).
log "Starting NuggiesSetup hotspot..."
hotspot_rc=0
( cd "$PROJECT_DIR" && python3 -m wifi_setup.wifi_manager --start-hotspot ) 2>&1 | tee -a "$LOG" || hotspot_rc="${PIPESTATUS[0]}"
if [[ "$hotspot_rc" -ne 0 ]]; then
    log "ERROR: Failed to start hotspot. Is NetworkManager running?"
    exit 1
fi

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

# Signal NM's dnsmasq to reload in case it started before the config was written.
pkill -HUP -f "dnsmasq" 2>/dev/null && log "Reloaded dnsmasq." || log "dnsmasq not running yet (OK)."

log "Starting setup display on matrix..."
python3 "$PROJECT_DIR/display/setup/main.py" >> "$LOG" 2>&1 &
DISPLAY_PID=$!
log "Setup display started (pid $DISPLAY_PID)."

log "Starting captive portal on port 80..."
# exec replaces this script with uvicorn — systemd then tracks uvicorn directly.
# The setup display process will be orphaned when uvicorn takes over; systemd
# will clean it up when the service stops.
log "HTTP access logs available via: journalctl -u nuggies-wifi-setup.service -f"
exec python3 -m uvicorn wifi_setup.captive_portal:app \
    --host 0.0.0.0 \
    --port 80 \
    --log-level info
