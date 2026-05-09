#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USER=$(whoami)
RGBMATRIX_REPO="/tmp/rpi-rgb-led-matrix"

cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# System packages
# ---------------------------------------------------------------------------
install_system_packages() {
    echo "--- Installing system packages..."
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y \
        python3-pip python3-pil python3-dev \
        python3-protobuf python3-pandas python3-requests \
        avahi-daemon git curl screen iptables
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

    echo "--- Installing Python packages (display — root, for sudo python3)..."
    sudo pip install -r requirements-display.txt --break-system-packages
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
    sudo pip install "$RGBMATRIX_REPO" --break-system-packages
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
}

# ---------------------------------------------------------------------------
# Port forwarding — 80 → 8000 (API)
# ---------------------------------------------------------------------------
setup_port_forwarding() {
    echo "--- Setting up port forwarding (80 → 8000)..."
    if ! sudo iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null; then
        sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000
        # Persist if iptables-persistent is available
        sudo netfilter-persistent save 2>/dev/null || true
        echo "Port forwarding rule added."
    else
        echo "Port forwarding rule already exists."
    fi
}

# ---------------------------------------------------------------------------
# Sudoers — allow pi to run display scripts with sudo and no password prompt
# ---------------------------------------------------------------------------
setup_sudoers() {
    echo "--- Configuring sudoers for display scripts..."
    SUDOERS_FILE="/etc/sudoers.d/nuggies-display"
    PYTHON=$(which python3)
    cat > /tmp/nuggies-display-sudoers <<EOF
# Allows the nuggies API (running as $USER) to start display scripts without a password prompt.
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/stocks/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/mta/main.py
$USER ALL=(ALL) NOPASSWD: $PYTHON $SCRIPT_DIR/display/clock/main.py
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
    mkdir -p "$SCRIPT_DIR/logs"
    echo "Log directory ready at $SCRIPT_DIR/logs"
}

# ---------------------------------------------------------------------------
# Frontend — npm install + point apiConfig at this Pi
# ---------------------------------------------------------------------------
install_frontend() {
    echo "--- Installing frontend packages..."
    cd "$SCRIPT_DIR/website"
    npm install
    cat > src/configs/apiConfig.js <<EOF
// Auto-generated by setup.sh
export const apiEndpoint = 'http://$HOSTNAME.local:8000'
EOF
    cd "$SCRIPT_DIR"
    echo "Frontend installed. API endpoint set to $HOSTNAME.local:8000"
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
init_settings
verify_display

echo ""
echo "========================================="
echo " Nuggies Pi Displays — setup complete!"
echo " Run: cd api && bash run_api.sh"
echo "========================================="
