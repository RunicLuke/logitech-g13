#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
sudo venv/bin/python3 << 'PYEOF'
from g13.device import G13Device
from g13.lcd import render_text, render_clock
g13 = G13Device()
g13.open()
g13.set_lcd(render_text("Hello G13!\nPi 5 Driver\nWorking!", font_size=12))
g13.close()
print("Done - check the LCD screen")
PYEOF
