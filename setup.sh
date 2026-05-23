#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USER=$(whoami)
RGBMATRIX_REPO="/tmp/rpi-rgb-led-matrix"

MODE=""
for arg in "$@"; do
  case "$arg" in
    --dev)  MODE="dev"  ;;
    --prod) MODE="prod" ;;
  esac
done

if [[ -z "$MODE" ]]; then
  echo "Usage: bash setup.sh --dev | --prod"
  echo ""
  echo "  --dev   Screen sessions via cron (API + webpack dev server)"
  echo "  --prod  Systemd service (API serves built React app)"
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
    pip install -r requirements-api.txt --break-system-packages

    echo "--- Installing Python packages (captive portal — root, for systemd service)..."
    sudo pip install -r requirements-api.txt --break-system-packages --upgrade

    echo "--- Installing Python packages (display — root, for sudo python3)..."
    sudo pip install -r requirements-display.txt --break-system-packages --upgrade
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
    cat > /tmp/nuggies-display-sudoers <<EOF
# Display scripts
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/stocks/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/mta/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/clock/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/weather/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/setup/main.py
# System commands called by the API
$USER ALL=(ALL) NOPASSWD: $BASH $SCRIPT_DIR/setup.sh
$USER ALL=(ALL) NOPASSWD: $REBOOT
EOF
    sudo install -m 0440 /tmp/nuggies-display-sudoers "$SUDOERS_FILE"
    rm /tmp/nuggies-display-sudoers
    echo "Sudoers entry written to $SUDOERS_FILE"
}

# ---------------------------------------------------------------------------
# Log directory
# ---------------------------------------------------------------------------
setup_logs() {
    echo "--- Creating log directory..."
    sudo mkdir -p /var/log/nuggies
    sudo chown "$USER":"$USER" /var/log/nuggies
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
# Run
# ---------------------------------------------------------------------------
install_system_packages
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
init_settings
verify_display

if [[ "$MODE" == "dev" ]]; then
    setup_dev
else
    setup_prod
fi

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
