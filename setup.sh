#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Re-exec as root if not already — ensures all internal sudo calls succeed
# without password prompts (important when triggered from the API or --update).
if [[ $EUID -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

USER="${SUDO_USER:-$(whoami)}"
RGBMATRIX_REPO="/tmp/rpi-rgb-led-matrix"

MODE=""
SUBCOMMAND=""
FORCE_REBOOT=""
for arg in "$@"; do
  case "$arg" in
    --dev)   MODE="dev"  ;;
    --prod)  MODE="prod" ;;
    --update)  SUBCOMMAND="update" ;;
    --reboot)  FORCE_REBOOT="1" ;;
  esac
done

if [[ -z "$MODE" && -z "$SUBCOMMAND" ]]; then
  echo "Usage: bash setup.sh --dev | --prod | --update"
  echo ""
  echo "  --dev     Full install: screen sessions (API + webpack dev server)"
  echo "  --prod    Full install: systemd service (API serves built React app)"
  echo "  --update  Pull latest code, reinstall deps, reapply sudoers"
  exit 1
fi

cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# System packages
# ---------------------------------------------------------------------------
install_system_packages() {
    echo "--- Installing system packages..."
    sudo apt update && sudo apt upgrade -y
    # Remove full dnsmasq if installed — it binds 0.0.0.0:53 and blocks NM's hotspot dnsmasq.
    # Only dnsmasq-base (binary only, no service) is needed for NM to run its own instance.
    sudo apt remove -y dnsmasq 2>/dev/null || true
    sudo apt install -y \
        python3-pip python3-pil python3-dev \
        python3-protobuf python3-pandas python3-requests \
        avahi-daemon git curl screen iptables \
        dnsmasq-base network-manager
    echo "System packages installed."
}

# ---------------------------------------------------------------------------
# Avahi / mDNS — make the Pi's <hostname>.local reachable and keep it reachable
# from phones. Phones aggressively sleep their mDNS resolver to save battery, so
# a .local lookup that works from a laptop silently times out from a phone that
# has not asked recently. We cannot change the phone, so we make the Pi's
# responder as resilient as possible:
#   * pin the advertised host-name to the system hostname (no "hostname-2"
#     rename collisions after a reboot or a duplicate-name blip),
#   * advertise on BOTH IPv4 and IPv6 (iOS prefers IPv6 mDNS and will fail the
#     lookup if only IPv4 is published).
# This is the single most effective server-side fix for "works everywhere but
# the phone" — the rest of that problem is router AP-isolation / band-splitting,
# which lives on the user's router, not here.
#
# Deliberately NOT changed: avahi's default rate-limiting is left in place (it
# only throttles replies, never the Pi's own traffic, and the default burst is
# already ample for a phone waking up), and the reflector stays OFF — it only
# matters on a multi-interface host, and these Pis have a single wlan0.
# ---------------------------------------------------------------------------
setup_avahi() {
    echo "--- Configuring Avahi (mDNS / .local) for reliable phone reachability..."

    # Advertise under the real system hostname (what the user types as .local).
    local HOST
    HOST="$(hostname)"

    sudo tee /etc/avahi/avahi-daemon.conf > /dev/null <<AVAHI
# Managed by nuggies_pi_displays setup.sh — hardened for phone mDNS reachability.
[server]
host-name=$HOST
domain-name=local
use-ipv4=yes
use-ipv6=yes

[publish]
publish-addresses=yes
publish-hinfo=yes
publish-workstation=yes
publish-aaaa-on-ipv4=yes
publish-a-on-ipv6=yes

[rlimits]
AVAHI

    sudo chmod 644 /etc/avahi/avahi-daemon.conf

    # Make sure the service is enabled and pick up the new config now.
    sudo systemctl enable avahi-daemon 2>/dev/null || true
    sudo systemctl restart avahi-daemon 2>/dev/null || true
    echo "Avahi configured and restarted — ${HOST}.local advertised on IPv4+IPv6."
}

# ---------------------------------------------------------------------------
# Node.js 18
# ---------------------------------------------------------------------------
install_node() {
    echo "--- Checking Node.js..."
    if command -v node &>/dev/null && [[ "$(node -v)" == "v22."* ]]; then
        echo "Node.js 22 already installed."
        return
    fi
    echo "Installing Node.js 22..."
    sudo apt remove -y nodejs npm 2>/dev/null || true
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt install -y nodejs
    echo "Node.js 22 installed."
}

# ---------------------------------------------------------------------------
# Python packages
# ---------------------------------------------------------------------------
install_python_packages() {
    echo "--- Installing Python packages (API)..."
    pip install -r requirements-api.txt --break-system-packages --ignore-installed

    echo "--- Installing Python packages (captive portal — root, for systemd service)..."
    pip install -r requirements-api.txt --break-system-packages --ignore-installed

    echo "--- Installing Python packages (display — root, for sudo python3)..."
    pip install -r requirements-display.txt --break-system-packages --ignore-installed
}

# ---------------------------------------------------------------------------
# rgbmatrix — clone + pip install as root
# ---------------------------------------------------------------------------
setup_rgbmatrix() {
    echo "--- Setting up rgbmatrix..."
    if [ ! -d "$RGBMATRIX_REPO" ]; then
        git clone https://github.com/hzeller/rpi-rgb-led-matrix.git "$RGBMATRIX_REPO"
    else
        echo "rgbmatrix repo already cloned."
    fi
    sudo pip install "$RGBMATRIX_REPO" --break-system-packages --ignore-installed
    echo "rgbmatrix installed."
}

# ---------------------------------------------------------------------------
# BDF fonts
# ---------------------------------------------------------------------------
copy_fonts() {
    echo "--- Copying BDF fonts..."
    mkdir -p display/fonts
    for font in 4x6.bdf 5x8.bdf 6x10.bdf; do
        if [ -f "$RGBMATRIX_REPO/fonts/$font" ]; then
            cp "$RGBMATRIX_REPO/fonts/$font" display/fonts/
            echo "  Copied $font"
        else
            echo "  Warning: $font not found in repo."
        fi
    done
    chmod 644 display/fonts/*.bdf 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Port forwarding — 80 → 8000 (API)
# ---------------------------------------------------------------------------
setup_port_forwarding() {
    echo "--- Setting up port forwarding (80 → 8000)..."
    sudo apt install -y iptables-persistent 2>/dev/null || true
    if ! sudo iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null; then
        sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000
        echo "Port forwarding rule added."
    else
        echo "Port forwarding rule already exists."
    fi
    sudo netfilter-persistent save
    echo "iptables rules persisted."
}

# ---------------------------------------------------------------------------
# Sudoers — allow pi to run display scripts with sudo and no password prompt
# ---------------------------------------------------------------------------
setup_sudoers() {
    echo "--- Configuring sudoers for display scripts and system commands..."
    SUDOERS_FILE="/etc/sudoers.d/nuggies-display"
    PYTHON=$(command -v python3)
    BASH=$(command -v bash)
    REBOOT=$(command -v reboot 2>/dev/null || echo /usr/sbin/reboot)
    SYSTEMCTL=$(command -v systemctl 2>/dev/null || echo /usr/bin/systemctl)
    CHMOD=$(command -v chmod 2>/dev/null || echo /usr/bin/chmod)
    IPTABLES=$(command -v iptables 2>/dev/null || echo /usr/sbin/iptables)
    rm -f /tmp/nuggies-display-sudoers
    cat > /tmp/nuggies-display-sudoers <<EOF
# Display scripts
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/clock/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/mta/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/sports/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/stocks/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/weather/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/setup/main.py
# System commands called by the API.
# The trailing '' and '*' BOTH matter: a command listed with no argument spec
# only matches an invocation with ZERO arguments, but the API always calls
# `setup.sh --update` (and --dev/--prod). Without an argument wildcard, sudo
# refuses the argument-bearing form with "a password is required" and the
# detached update silently never runs. The '*' authorises the flag argument;
# the script path is fixed so this does not broaden the grant to other scripts.
$USER ALL=(ALL) NOPASSWD: $BASH $SCRIPT_DIR/setup.sh, $BASH $SCRIPT_DIR/setup.sh *
$USER ALL=(ALL) NOPASSWD: $REBOOT
$USER ALL=(ALL) NOPASSWD: $SYSTEMCTL restart nuggies-wifi-setup.service
$USER ALL=(ALL) NOPASSWD: $SYSTEMCTL restart nuggies-api.service
# Kill/sweep display processes (which run as root via sudo)
$USER ALL=(ALL) NOPASSWD: /bin/kill
$USER ALL=(ALL) NOPASSWD: /usr/bin/kill
$USER ALL=(ALL) NOPASSWD: /usr/bin/pkill
$USER ALL=(ALL) NOPASSWD: /usr/bin/pgrep
# Narrowly-scoped privileged actions the API issues.
# chmod is scoped to the single settings file factory reset repairs; a bare
# chmod grant would be equivalent to root (chmod on /etc/shadow, or on setup.sh).
# iptables is granted read-only: mutating forms (-A/-D/-I/-F) stay ungranted
# because every mutation in the WiFi flow already happens as root under systemd.
$USER ALL=(ALL) NOPASSWD: $CHMOD 666 $SCRIPT_DIR/api/settings.json
$USER ALL=(ALL) NOPASSWD: $IPTABLES -t nat -L PREROUTING -n
EOF
    install -m 0440 /tmp/nuggies-display-sudoers "$SUDOERS_FILE"
    rm -f /tmp/nuggies-display-sudoers
    echo "Sudoers entry written to $SUDOERS_FILE"
}

# ---------------------------------------------------------------------------
# Log directory
# ---------------------------------------------------------------------------
setup_logs() {
    echo "--- Creating log directory..."
    mkdir -p /var/log/nuggies
    # Display processes run as daemon user via sudo, API runs as pi —
    # make the directory writable by everyone who needs to log.
    chmod 777 /var/log/nuggies
    echo "Log directory ready at /var/log/nuggies"
}

# ---------------------------------------------------------------------------
# Frontend — npm install + point apiConfig at this Pi
# ---------------------------------------------------------------------------
install_frontend() {
    echo "--- Installing frontend packages..."
    cd "$SCRIPT_DIR/website"
    npm install
    cd "$SCRIPT_DIR"
    echo "Frontend installed."
}

# ---------------------------------------------------------------------------
# Frontend build — produce website/dist/ for the captive portal to serve
# ---------------------------------------------------------------------------
build_frontend() {
    echo "--- Building frontend..."
    cd "$SCRIPT_DIR/website"
    npm run build
    cd "$SCRIPT_DIR"
    echo "Frontend built to website/dist/"
}

# ---------------------------------------------------------------------------
# WiFi setup service — install + enable the captive-portal systemd unit
# ---------------------------------------------------------------------------
install_wifi_setup_service() {
    echo "--- Installing WiFi setup service..."
    SERVICE_DST="/etc/systemd/system/nuggies-wifi-setup.service"

    sudo tee "$SERVICE_DST" > /dev/null <<SERVICE
[Unit]
Description=Nuggies WiFi Setup / Captive Portal
Documentation=https://github.com/nuggies/nuggies_pi_displays
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=/bin/bash $SCRIPT_DIR/scripts/wifi_setup_service.sh
WorkingDirectory=$SCRIPT_DIR
User=root
StandardOutput=journal
StandardError=journal
Restart=no

[Install]
WantedBy=multi-user.target
SERVICE

    sudo chmod 644 "$SERVICE_DST"
    sudo chmod +x "$SCRIPT_DIR/scripts/wifi_setup_service.sh"
    sudo systemctl daemon-reload
    sudo systemctl enable nuggies-wifi-setup.service
    echo "WiFi setup service installed and enabled."
}

# ---------------------------------------------------------------------------
# Settings — copy defaults if settings.json doesn't exist yet
# ---------------------------------------------------------------------------
init_settings() {
    echo "--- Initialising settings..."
    if [ ! -f api/settings.json ]; then
        cp api/settings.default.json api/settings.json
        echo "Created api/settings.json from defaults."
    else
        echo "api/settings.json already exists, skipping."
    fi
    if [ ! -f dev_config.json ]; then
        cp dev_config.default.json dev_config.json
        echo "Created dev_config.json from defaults."
    else
        echo "dev_config.json already exists, skipping."
    fi
    # Ensure settings files are owned by the API user (pi), not root
    chown "$USER":"$USER" api/settings.json api/settings.json.lock 2>/dev/null || true
    chown "$USER":"$USER" dev_config.json 2>/dev/null || true
    chmod 644 api/settings.json
}

# ---------------------------------------------------------------------------
# Verify display — flash "Ready!" on the matrix for 5 seconds
# ---------------------------------------------------------------------------
verify_display() {
    echo "--- Verifying display..."
    sudo python3 - <<'EOF'
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from rgbmatrix import graphics
from pathlib import Path
import time

options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = "adafruit-hat"
matrix = RGBMatrix(options=options)
canvas = matrix.CreateFrameCanvas()

font_path = Path(__file__).parent / "display/fonts/5x8.bdf" if False else Path("/tmp/rpi-rgb-led-matrix/fonts/5x8.bdf")
font = graphics.Font()
if font_path.exists():
    font.LoadFont(str(font_path))

green = graphics.Color(0, 255, 0)
white = graphics.Color(255, 255, 255)

graphics.DrawText(canvas, font, 2, 10, green, "Nuggies")
graphics.DrawText(canvas, font, 8, 20, white, "Ready!")
canvas = matrix.SwapOnVSync(canvas)

time.sleep(5)
matrix.Clear()
EOF
    echo "Display check complete."
}

# ---------------------------------------------------------------------------
# Cron helper — add an entry only if it isn't already present
# ---------------------------------------------------------------------------
add_cron_if_missing() {
    local entry="$1"
    local label="$2"
    if crontab -l 2>/dev/null | grep -qF "$entry"; then
        echo "  [skip] Cron already has: $label"
    else
        (crontab -l 2>/dev/null || true; echo "$entry") | crontab -
        echo "  [added] Cron: $label"
    fi
}

# ---------------------------------------------------------------------------
# Dev mode — screen sessions via @reboot cron
# ---------------------------------------------------------------------------
setup_dev() {
    echo "--- Setting up dev environment (screen cron sessions)..."
    sudo apt install -y screen 2>/dev/null || true

    local api_entry="@reboot sleep 10 && screen -dmS nuggies-api bash -c 'cd $SCRIPT_DIR/api && bash run_api.sh'"
    local web_entry="@reboot sleep 10 && screen -dmS nuggies-web bash -c 'cd $SCRIPT_DIR/website && npm start'"

    add_cron_if_missing "$api_entry" "nuggies-api screen session"
    add_cron_if_missing "$web_entry" "nuggies-web screen session"

    echo "Dev cron jobs installed."
    echo "  Attach API:     screen -r nuggies-api"
    echo "  Attach webpack: screen -r nuggies-web"
    echo "  Start now:      screen -dmS nuggies-api bash -c 'cd $SCRIPT_DIR/api && bash run_api.sh'"
}

# ---------------------------------------------------------------------------
# Prod mode — systemd service for the API (React app served by FastAPI)
# ---------------------------------------------------------------------------
setup_prod() {
    echo "--- Installing production systemd service..."

    sudo tee /etc/systemd/system/nuggies-api.service > /dev/null <<SERVICE
[Unit]
Description=Nuggies Pi Displays API
After=network.target nuggies-wifi-setup.service
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR/api
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
StandardOutput=append:$SCRIPT_DIR/logs/api.log
StandardError=append:$SCRIPT_DIR/logs/api.log

[Install]
WantedBy=multi-user.target
SERVICE

    sudo systemctl daemon-reload
    sudo systemctl enable nuggies-api.service
    sudo systemctl restart nuggies-api.service
    echo "Production API service installed, enabled, and started."
}

# ---------------------------------------------------------------------------
# WiFi power-save — disable so the WiFi chip doesn't cause periodic interrupts
# that bleed into the RGB matrix timing.
# ---------------------------------------------------------------------------
disable_wifi_power_save() {
    echo "--- Disabling WiFi power management..."
    sudo tee /etc/systemd/system/nuggies-wifi-powersave.service > /dev/null <<SERVICE
[Unit]
Description=Disable WiFi power save (prevents RGB matrix bleed)
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/iw wlan0 set power_save off
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE
    sudo systemctl daemon-reload
    sudo systemctl enable nuggies-wifi-powersave.service
    sudo systemctl start  nuggies-wifi-powersave.service
    echo "WiFi power save disabled."
}

# ---------------------------------------------------------------------------
# isolcpus — dedicate CPU core 3 to the RGB matrix for glitch-free refresh.
# ---------------------------------------------------------------------------
setup_isolcpus() {
    local CMDLINE=""
    if [[ -f /boot/firmware/cmdline.txt ]]; then
        CMDLINE="/boot/firmware/cmdline.txt"
    else
        CMDLINE="/boot/cmdline.txt"
    fi

    if grep -q "isolcpus" "$CMDLINE"; then
        echo "isolcpus already set in $CMDLINE, skipping."
        return
    fi

    echo "--- Adding isolcpus=3 to $CMDLINE..."
    sudo sed -i 's/$/ isolcpus=3/' "$CMDLINE"
    echo "isolcpus=3 added. Takes effect after reboot."
}

# ---------------------------------------------------------------------------
# Disable onboard audio — GPIO 18 (used for audio PWM) conflicts with the
# RGB matrix data lines causing random pixel noise / speckling.
# ---------------------------------------------------------------------------
disable_onboard_audio() {
    local CONFIG=""
    if [[ -f /boot/firmware/config.txt ]]; then
        CONFIG="/boot/firmware/config.txt"
    elif [[ -f /boot/config.txt ]]; then
        CONFIG="/boot/config.txt"
    else
        echo "Cannot find config.txt, skipping audio disable."
        return
    fi

    if grep -q "^dtparam=audio=off" "$CONFIG"; then
        echo "Onboard audio already disabled in $CONFIG, skipping."
        return
    fi

    echo "--- Disabling onboard audio (conflicts with RGB matrix)..."
    # Replace audio=on with audio=off, or add it if not present
    if grep -q "^dtparam=audio=" "$CONFIG"; then
        sudo sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$CONFIG"
    else
        echo "dtparam=audio=off" | sudo tee -a "$CONFIG" > /dev/null
    fi
    echo "Onboard audio disabled. Takes effect after reboot."
}

# ---------------------------------------------------------------------------
# Marker ownership — every marker file in the WiFi flow is written by *both*
# the root boot script and the API (which runs as $USER), so each one has to be
# owned by $USER:$USER for both writers to work.
#
# The project root is drwxrwxr-x pi pi, so $USER can *unlink* a root-owned
# marker but cannot *open it for writing* — marker deletes succeed while marker
# writes fail. Normalising ownership here removes that asymmetry.
#
# This only ever changes ownership: a marker that does not exist is NOT created,
# because creating one would change the boot verdict.
# ---------------------------------------------------------------------------
MARKER_PATHS=(
    ".wifi_configured"
    ".force_portal"
    ".factory_wifi_reset"
    "wifi_setup/.last_scan.json"
)

normalize_marker_ownership() {
    echo "--- Normalising marker ownership to $USER:$USER..."
    local rel path
    for rel in "${MARKER_PATHS[@]}"; do
        path="$SCRIPT_DIR/$rel"
        if [[ -e "$path" ]]; then
            chown "$USER":"$USER" "$path"
            echo "    $rel -> $USER:$USER"
        else
            echo "    $rel absent, not created."
        fi
    done
}

# ---------------------------------------------------------------------------
# Tree ownership — hand the repository back to $USER after any root-level git
# operation. run_update() pulls as root, while api/helpers/update_check.py runs
# `git fetch origin` as $USER. Root-owned objects under .git accumulate and
# eventually break that fetch, so the update path silently degrades its own
# ability to notice that updates exist.
#
# .git is the mandatory part. The working tree is handed back too, excluding
# website/node_modules (~270MB of npm-owned files that no $USER-level git
# operation needs) so the pass stays cheap on a Pi.
# ---------------------------------------------------------------------------
restore_tree_ownership() {
    echo "--- Restoring tree ownership to $USER:$USER..."
    chown -R "$USER":"$USER" "$SCRIPT_DIR/.git"
    echo "    .git -> $USER:$USER"

    find "$SCRIPT_DIR" \
        -path "$SCRIPT_DIR/.git" -prune -o \
        -path "$SCRIPT_DIR/website/node_modules" -prune -o \
        -exec chown -h "$USER":"$USER" {} +
    echo "    working tree -> $USER:$USER (website/node_modules skipped)"
}

# ---------------------------------------------------------------------------
# WiFi flag — if WiFi is already connected, ensure the .wifi_configured flag
# exists so the API auto-starts the display on boot.
# Ownership is handled by normalize_marker_ownership().
# ---------------------------------------------------------------------------
ensure_wifi_flag() {
    WIFI_FLAG="$SCRIPT_DIR/.wifi_configured"
    if [[ -f "$WIFI_FLAG" ]]; then
        echo "--- WiFi flag already exists, skipping."
        return
    fi

    # Check if wlan0 is connected
    if nmcli -t -f STATE general 2>/dev/null | grep -q "connected"; then
        echo "--- WiFi is connected, creating .wifi_configured flag..."
        touch "$WIFI_FLAG"
        echo "WiFi flag created."
    else
        echo "--- WiFi not connected, skipping .wifi_configured flag."
    fi
}

# ---------------------------------------------------------------------------
# Verify permissions — probe every grant and every writable path this runtime
# depends on, print one pass/fail line per item, and exit 1 if any item failed.
#
# Why this fails loudly at provisioning time: the runtime failure mode is
# silent. A refused `sudo -n` inside an HTTP handler returns a non-zero code
# that nobody reads, so today the operator finishes setup believing it worked
# and the *user* discovers the gap later — as an action that reports success
# and changes nothing. Provisioning time is the only moment a human is present
# who can act on the information, so any gap has to be surfaced here, now.
#
# All grant probes use the non-interactive refusal probe (sudo's -n flag), never
# the list-privileges probe (sudo's -l flag): pi is in the sudo group and matches
# (ALL:ALL) ALL, so the list-privileges form exits 0 even for commands that would
# prompt for a password — it always reports a pass and is not a valid NOPASSWD
# probe. The -n form refuses with "sudo: a password is required" whenever no
# NOPASSWD rule matches, which is the exact condition each check is testing.
#
# setup.sh runs as root, but the API runs as $USER, so every probe is executed
# *as $USER* via `sudo -u "$USER" sudo -n …` to reproduce the runtime caller.
# ---------------------------------------------------------------------------
verify_permissions() {
    echo "--- Verifying permissions (provisioning-time gate)..."

    local SUDOERS_FILE="/etc/sudoers.d/nuggies-display"
    local PYTHON BASH REBOOT SYSTEMCTL CHMOD IPTABLES
    PYTHON=$(command -v python3)
    BASH=$(command -v bash)
    REBOOT=$(command -v reboot 2>/dev/null || echo /usr/sbin/reboot)
    SYSTEMCTL=$(command -v systemctl 2>/dev/null || echo /usr/bin/systemctl)
    CHMOD=$(command -v chmod 2>/dev/null || echo /usr/bin/chmod)
    IPTABLES=$(command -v iptables 2>/dev/null || echo /usr/sbin/iptables)

    local failures=0

    # -- helper: run an argv as $USER through `sudo -n` and classify the result.
    # A refused grant prints "a password is required" on stderr; anything else
    # (success, or a command's own non-zero exit) means the grant matched.
    _probe_nopasswd() {
        local label="$1"; shift
        local err
        err=$(sudo -u "$USER" sudo -n "$@" 2>&1 >/dev/null)
        if printf '%s' "$err" | grep -q "a password is required"; then
            echo "    [PROBED ] FAIL  $label — sudo refused (no matching NOPASSWD grant): $*"
            failures=$((failures + 1))
        else
            echo "    [PROBED ] pass  $label"
        fi
    }

    # -- helper: probe `bash setup.sh <arg>` with a sentinel argument. The runtime
    # never invokes setup.sh bare — it always passes --update/--dev/--prod — so the
    # probe must carry an argument to exercise the same match the grant needs to
    # cover. A sentinel like --verify-noop matches neither MODE nor SUBCOMMAND, so
    # the script prints its usage banner and exits 1 without doing any work (running
    # a real --update here would trigger an actual update). This still proves the
    # grant authorises the argument-bearing form: an argument-free NOPASSWD grant
    # matches any args, so if a future edit tightens it to zero args (trailing ""),
    # this probe starts failing exactly as the real invocations would. Distinguish
    # the legitimate exit-1 from a sudo refusal purely by the password message.
    _probe_setup_sh() {
        local label="bash setup.sh <arg> (argument-bearing form, usage-banner exit)"
        local err
        err=$(sudo -u "$USER" sudo -n "$BASH" "$SCRIPT_DIR/setup.sh" --verify-noop 2>&1 >/dev/null)
        if printf '%s' "$err" | grep -q "a password is required"; then
            echo "    [PROBED ] FAIL  $label — sudo refused (no matching NOPASSWD grant)"
            failures=$((failures + 1))
        else
            echo "    [PROBED ] pass  $label"
        fi
    }

    # -- helper: assert an exact line is present in the installed sudoers file.
    # Used for grants that cannot be executed as a live test (they would seize
    # the LED matrix, reboot the device, or drop the WiFi association). Labelled
    # ASSERTED, never PROBED, so nobody mistakes a file match for an execution.
    _assert_sudoers_line() {
        local label="$1"; local expected="$2"
        if grep -qF "$expected" "$SUDOERS_FILE" 2>/dev/null; then
            echo "    [ASSERTED] pass  $label"
        else
            echo "    [ASSERTED] FAIL  $label — expected line absent from $SUDOERS_FILE: $expected"
            failures=$((failures + 1))
        fi
    }

    # === PROBED: granted argv executed as $USER, each read-only or idempotent ===
    _probe_nopasswd "chmod 666 api/settings.json" \
        "$CHMOD" 666 "$SCRIPT_DIR/api/settings.json"
    _probe_nopasswd "iptables -t nat -L PREROUTING -n (read-only)" \
        "$IPTABLES" -t nat -L PREROUTING -n
    _probe_nopasswd "kill -0 (/bin/kill)" \
        /bin/kill -0 "$$"
    _probe_nopasswd "kill -0 (/usr/bin/kill)" \
        /usr/bin/kill -0 "$$"
    _probe_nopasswd "pkill -0 (no-match sentinel)" \
        /usr/bin/pkill -0 -f nuggies-verify-no-match
    _probe_nopasswd "pgrep (no-match sentinel)" \
        /usr/bin/pgrep -f nuggies-verify-no-match
    _probe_setup_sh

    # === ASSERTED: grants that cannot be executed as a live test ===
    # Six display scripts (they seize the LED matrix):
    _assert_sudoers_line "grant: display/clock/main.py" \
        "$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/clock/main.py"
    _assert_sudoers_line "grant: display/mta/main.py" \
        "$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/mta/main.py"
    _assert_sudoers_line "grant: display/sports/main.py" \
        "$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/sports/main.py"
    _assert_sudoers_line "grant: display/stocks/main.py" \
        "$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/stocks/main.py"
    _assert_sudoers_line "grant: display/weather/main.py" \
        "$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/weather/main.py"
    _assert_sudoers_line "grant: display/setup/main.py" \
        "$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/setup/main.py"
    # reboot (it reboots the device):
    _assert_sudoers_line "grant: reboot" \
        "$USER ALL=(ALL) NOPASSWD: $REBOOT"
    # systemctl restart of the wifi-setup service (it drops the WiFi association);
    # the .service suffix is load-bearing — the bare form does not match:
    _assert_sudoers_line "grant: systemctl restart nuggies-wifi-setup.service" \
        "$USER ALL=(ALL) NOPASSWD: $SYSTEMCTL restart nuggies-wifi-setup.service"
    # systemctl restart of the API service (the /system/restart-api endpoint);
    # asserted rather than probed because restarting mid-provision would kill setup:
    _assert_sudoers_line "grant: systemctl restart nuggies-api.service" \
        "$USER ALL=(ALL) NOPASSWD: $SYSTEMCTL restart nuggies-api.service"

    # === WRITABILITY: markers openable/creatable by $USER, plus .git ownership ===
    local rel path dir
    for rel in "${MARKER_PATHS[@]}"; do
        path="$SCRIPT_DIR/$rel"
        dir="$(dirname "$path")"
        if [[ -e "$path" ]]; then
            # Existing marker: must be openable for writing by $USER (append, so
            # the probe never truncates or alters the marker's contents).
            if sudo -u "$USER" test -w "$path" && \
               sudo -u "$USER" bash -c ": >> \"$path\"" 2>/dev/null; then
                echo "    [WRITABLE] pass  marker exists and is $USER-writable: $rel"
            else
                echo "    [WRITABLE] FAIL  marker exists but is NOT $USER-writable: $rel"
                failures=$((failures + 1))
            fi
        else
            # Absent marker: $USER must be able to create and remove it in its
            # directory. Create then immediately remove so the verdict is not
            # changed by inventing a marker.
            if sudo -u "$USER" bash -c "touch \"$path\" && rm -f \"$path\"" 2>/dev/null; then
                echo "    [WRITABLE] pass  marker absent but $USER can create/remove it: $rel"
            else
                echo "    [WRITABLE] FAIL  marker absent and $USER cannot create it in $dir: $rel"
                failures=$((failures + 1))
            fi
        fi
    done

    # .git must be $USER-owned so the $USER-level `git fetch origin` keeps working.
    local git_owner
    git_owner=$(stat -c '%U' "$SCRIPT_DIR/.git" 2>/dev/null || echo "?")
    if [[ "$git_owner" == "$USER" ]]; then
        echo "    [WRITABLE] pass  .git is owned by $USER"
    else
        echo "    [WRITABLE] FAIL  .git is owned by '$git_owner', expected $USER"
        failures=$((failures + 1))
    fi

    if [[ "$failures" -ne 0 ]]; then
        echo ""
        echo "!!! verify_permissions: $failures item(s) FAILED. Provisioning is incomplete."
        echo "!!! Fix the grants/ownership above and re-run: sudo bash setup.sh --update"
        exit 1
    fi
    echo "--- verify_permissions: all items passed."
}

# ---------------------------------------------------------------------------
# Update — pull latest code, reinstall deps, reapply sudoers
# ---------------------------------------------------------------------------
run_update() {
    echo "========================================="
    echo " Nuggies Pi Displays — update [$(date '+%Y-%m-%d %H:%M:%S')]"
    echo "========================================="

    # Failure sentinel via EXIT trap: if run_update exits before writing the
    # COMPLETE sentinel (any `exit 1`, or a `set -e` abort on a failed step),
    # emit a FAILED marker so the web UI's update modal can show "update failed"
    # instead of spinning on "updating" forever. _UPDATE_DONE is set to 1 right
    # after the COMPLETE sentinel so the trap stays quiet on the success path.
    _UPDATE_DONE=0
    trap '[[ "$_UPDATE_DONE" == "1" ]] || echo "=== NUGGIES UPDATE FAILED ==="' EXIT

    echo "--- Pulling latest code..."
    # A plain `git pull` aborts if the tree has drifted — setup.sh itself
    # rewrites tracked file modes (chmod/chown) and a prior root-level pull can
    # leave a dirty/diverged tree. Fetch + hard-reset onto the tracked remote
    # branch so the update lands regardless of local mode/content drift.
    if ! git -C "$SCRIPT_DIR" fetch origin --prune; then
        echo "!!! git fetch failed. Aborting update." >&2
        exit 1
    fi
    # Resolve upstream (e.g. origin/main), falling back to origin/<branch>.
    if UPSTREAM=$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) && [[ -n "$UPSTREAM" ]]; then
        TARGET="$UPSTREAM"
    else
        BRANCH=$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
        TARGET="origin/$BRANCH"
        echo "No upstream configured; falling back to $TARGET"
    fi
    if ! git -C "$SCRIPT_DIR" reset --hard "$TARGET"; then
        echo "!!! git reset --hard $TARGET failed. Aborting update." >&2
        exit 1
    fi
    echo "Updated working tree to $TARGET."

    # The reset just ran as root; hand the tree back before anything else so the
    # $USER-level `git fetch origin` in api/helpers/update_check.py keeps working.
    restore_tree_ownership

    echo "--- Installing Python dependencies..."
    pip3 install --break-system-packages --ignore-installed -r "$SCRIPT_DIR/requirements-api.txt"
    pip3 install --break-system-packages --ignore-installed -r "$SCRIPT_DIR/requirements-display.txt"

    echo "--- Installing frontend dependencies..."
    cd "$SCRIPT_DIR/website"
    npm install
    # Prod serves the built bundle from website/dist, so it must be rebuilt on
    # update or the served UI stays stale. Dev serves from the webpack dev
    # server (no dist to refresh), so skip the build there to save time on the Pi.
    if systemctl list-unit-files nuggies-api.service &>/dev/null \
       && systemctl is-enabled --quiet nuggies-api.service 2>/dev/null; then
        echo "--- Building frontend (prod)..."
        npm run build
        # The build ran as root (setup.sh re-execs as root), so dist/ is now
        # root-owned — but restore_tree_ownership already ran before this point.
        # Hand the built bundle back to $USER so the tree stays consistently
        # $USER-owned (webpack's clean:true and $USER-level git both need it).
        chown -R "$USER":"$USER" "$SCRIPT_DIR/website/dist"
    else
        echo "--- Skipping frontend build (dev mode: served by webpack dev server)."
    fi
    cd "$SCRIPT_DIR"

    echo "--- Reapplying sudoers..."
    setup_sudoers

    echo "--- Checking hardware config..."
    setup_avahi
    setup_isolcpus
    disable_onboard_audio
    setup_logs
    ensure_wifi_flag
    normalize_marker_ownership
    init_settings

    # Verify the grants and ownership this update just (re)applied, and fail
    # loudly if any of it is missing. Done BEFORE restart/reboot so a gap is
    # surfaced in the update log rather than lost to the restart.
    verify_permissions

    echo ""
    echo "[$(date '+%H:%M:%S')] Update complete — applying to running processes."
    # Completion sentinel: written BEFORE any reboot/restart so it is always in
    # the log regardless of path. The web UI's update modal watches for this to
    # tell the user the update finished and the modal is safe to close. If a
    # reboot follows, the connection drops (which the modal already treats as
    # "rebooting"); if not (dev / no-reboot), this is the clean "done" signal.
    echo "=== NUGGIES UPDATE COMPLETE ==="
    _UPDATE_DONE=1  # suppress the EXIT-trap failure sentinel on the success path

    # Forced reboot (passed by callers that MUST come up fresh regardless of
    # environment — e.g. factory reset, which wiped settings/WiFi and needs to
    # boot into the setup portal). This bypasses the dev/prod detection below so
    # it reboots even on a dev device (where the plain update would not).
    if [[ -n "$FORCE_REBOOT" ]]; then
        echo "[$(date '+%H:%M:%S')] --reboot requested — rebooting now..."
        reboot
        exit 0
    fi

    # Apply the new code to the running processes.
    #
    # Detect prod by whether the systemd unit FILE exists, NOT by
    # `systemctl is-enabled --quiet`. The latter is unreliable: it exits non-zero
    # for states like "enabled-runtime"/"alias" and during transient states mid
    # update, which silently sent prod devices down the dev branch — leaving the
    # API running stale in-memory code after a "successful" update (new code on
    # disk, old process never restarted). Unit-file existence is unambiguous.
    if systemctl list-unit-files nuggies-api.service >/dev/null 2>&1 && \
       [[ -f /etc/systemd/system/nuggies-api.service ]]; then
        echo "[$(date '+%H:%M:%S')] Prod detected — rebooting to apply update..."
        # Reboot brings up API, display, and the freshly-built bundle on the new
        # code in one clean step. The API invoked this script detached
        # (start_new_session), so this reboot does not race the caller.
        #
        # Belt-and-suspenders: if `reboot` fails to take effect (returns), fall
        # back to an explicit service restart so the new code still loads rather
        # than leaving a stale process — the exact failure that made earlier
        # web-UI updates appear to do nothing.
        if ! reboot; then
            echo "[$(date '+%H:%M:%S')] reboot failed — restarting services directly" >&2
            systemctl restart nuggies-api.service || true
        fi
    else
        echo "[$(date '+%H:%M:%S')] Dev mode: API runs --reload and webpack rebuilds; no restart."
    fi
}

if [[ "$SUBCOMMAND" == "update" ]]; then
    run_update
    exit 0
fi

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
install_system_packages
setup_avahi
install_node
install_python_packages
setup_rgbmatrix
copy_fonts
setup_port_forwarding
setup_sudoers
setup_logs
install_frontend
build_frontend
install_wifi_setup_service
disable_wifi_power_save
setup_isolcpus
disable_onboard_audio
init_settings
verify_display
ensure_wifi_flag
normalize_marker_ownership

if [[ "$MODE" == "dev" ]]; then
    setup_dev
else
    setup_prod
fi

# Verify every grant and writable path before announcing success — this is the
# last step of the fresh-install path, and it exits non-zero (before the reboot
# below) if anything the runtime depends on is missing.
verify_permissions

echo ""
echo "========================================="
echo " Nuggies Pi Displays — setup complete!"
if [[ "$MODE" == "dev" ]]; then
    echo " Dev mode: reboot to start screen sessions, or run:"
    echo "   screen -dmS nuggies-api bash -c 'cd api && bash run_api.sh'"
    echo "   screen -dmS nuggies-web bash -c 'cd website && npm start'"
else
    echo " Prod mode: nuggies-api.service is running."
    echo "   Status: sudo systemctl status nuggies-api.service"
fi
echo "========================================="
echo ""
echo "Rebooting in 30 seconds... (Ctrl+C to cancel)"
sleep 30
sudo reboot
