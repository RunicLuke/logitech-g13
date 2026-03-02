#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
sudo venv/bin/python3 << 'PYEOF'
from g13.device import G13Device
from g13.lcd import render_system_stats
g13 = G13Device()
g13.open()
g13.set_lcd(render_system_stats())
g13.close()
print("System stats displayed on LCD")
PYEOF
