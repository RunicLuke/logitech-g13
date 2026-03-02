#!/bin/bash
# Usage: bash test_color.sh [color] [brightness%]
# Colors: red, green, blue, white, off, etc.
# Brightness: 0-100 (default 100)
# Examples:
#   bash test_color.sh red
#   bash test_color.sh blue 50
#   bash test_color.sh 255 100 0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
sudo venv/bin/python3 - "$@" << 'PYEOF'
import sys
from g13.device import G13Device
colors = {"red":(255,0,0),"green":(0,255,0),"blue":(0,0,255),"white":(255,255,255),"off":(0,0,0),"cyan":(0,255,255),"yellow":(255,255,0),"purple":(128,0,255),"orange":(255,128,0),"pink":(255,64,128)}
args = sys.argv[1:]
if not args:
    print(f"Usage: test_color.sh <color> [brightness%]")
    print(f"Colors: {', '.join(colors.keys())} or R G B values")
    sys.exit(1)
brightness = 1.0
if len(args) >= 2:
    try:
        b_val = int(args[-1])
        if 0 <= b_val <= 100 and (len(args) == 2 or len(args) == 4):
            brightness = b_val / 100.0
            args = args[:-1]
    except ValueError:
        pass
if len(args) == 3:
    r,g,b = int(args[0]),int(args[1]),int(args[2])
elif args[0] in colors:
    r,g,b = colors[args[0]]
else:
    print(f"Unknown color: {args[0]}")
    sys.exit(1)
g13 = G13Device()
g13.open()
g13.set_all_colors(r, g, b, brightness)
g13.close()
print(f"Color set to ({r},{g},{b}) brightness={int(brightness*100)}%")
PYEOF
