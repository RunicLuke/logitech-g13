#!/bin/bash
# Reads G13 key presses for 10 seconds and prints them
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
sudo venv/bin/python3 << 'PYEOF'
import time
from g13.device import G13Device
g13 = G13Device()
g13.open()
print("Press G-keys for 10 seconds...")
end = time.time() + 10
while time.time() < end:
    result = g13.read_keys_diff()
    if result:
        pressed, released, jx, jy = result
        if pressed:
            print(f"  Pressed: {pressed}")
        if released:
            print(f"  Released: {released}")
        if abs(jx - 128) > 30 or abs(jy - 128) > 30:
            print(f"  Joystick: x={jx} y={jy}")
    time.sleep(0.01)
g13.close()
print("Done")
PYEOF
