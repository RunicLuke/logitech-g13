#!/bin/bash
# Logitech G13 Driver Setup Script for Raspberry Pi
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "=== Logitech G13 Driver Setup ==="
echo ""

# Check if running as root for system-level setup
if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo for full setup (udev rules + systemd service)."
    echo "Running in user-only mode (venv + dependencies)..."
    echo ""
    SYSTEM_SETUP=false
else
    SYSTEM_SETUP=true
fi

# Setup venv and install dependencies
echo "[1/4] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --quiet hidapi Pillow
echo "  Dependencies installed."

# udev rule for non-root access
if [ "$SYSTEM_SETUP" = true ]; then
    echo "[2/4] Installing udev rule..."
    cat > /etc/udev/rules.d/91-g13.rules << 'EOF'
# Logitech G13 - allow non-root access
SUBSYSTEM=="usb", ATTR{idVendor}=="046d", ATTR{idProduct}=="c21c", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c21c", MODE="0666"
EOF
    udevadm control --reload-rules
    udevadm trigger
    echo "  udev rules installed. You may need to unplug/replug the G13."

    # Ensure uinput is accessible
    echo "[3/4] Setting up uinput permissions..."
    if ! grep -q "uinput" /etc/modules-load.d/*.conf 2>/dev/null; then
        echo "uinput" > /etc/modules-load.d/uinput.conf
    fi
    cat > /etc/udev/rules.d/92-uinput.rules << 'EOF'
KERNEL=="uinput", MODE="0666"
EOF
    udevadm control --reload-rules
    modprobe uinput 2>/dev/null || true
    chmod 666 /dev/uinput 2>/dev/null || true
    echo "  uinput permissions configured."

    # Systemd service
    echo "[4/4] Installing systemd service..."
    cat > /etc/systemd/system/g13.service << EOF
[Unit]
Description=Logitech G13 Driver Daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python -m g13.daemon
WorkingDirectory=$SCRIPT_DIR
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable g13.service
    echo "  Service installed and enabled."
    echo ""
    echo "To start now:  sudo systemctl start g13"
    echo "To view logs:  sudo journalctl -u g13 -f"
else
    echo "[2/4] Skipping udev rules (need sudo)"
    echo "[3/4] Skipping uinput setup (need sudo)"
    echo "[4/4] Skipping systemd service (need sudo)"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Quick test (may need sudo if udev rules aren't set):"
echo "  source $VENV_DIR/bin/activate"
echo "  python -m g13.cli test"
echo ""
echo "Start daemon manually:"
echo "  sudo $VENV_DIR/bin/python -m g13.daemon"
echo ""
echo "CLI commands (while daemon is running):"
echo "  python -m g13.cli lcd \"Hello World\"    # Display text"
echo "  python -m g13.cli color blue            # Set backlight"
echo "  python -m g13.cli mode clock            # Show clock"
echo "  python -m g13.cli mode stats            # Show system stats"
echo ""
