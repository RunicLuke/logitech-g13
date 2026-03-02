#!/bin/bash
# Press the top row buttons to see what they register as
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
sudo venv/bin/python3 << 'PYEOF'
import time
from g13.device import G13Device, KEY_MAP

# Show all key names we know about
print("Known keys in our map:")
for bit, name in sorted(KEY_MAP.items()):
    print(f"  bit {bit:2d}: {name}")
print()
print("Now press the top row buttons one at a time (15 seconds)...")
print("Press each button slowly so we can see which name it maps to.")
print()

g13 = G13Device()
g13.open()
g13.dev.set_nonblocking(True)

end = time.time() + 15
prev = set()
while time.time() < end:
    data = g13.dev.read(8)
    if data and len(data) >= 8:
        # Show raw bytes too so we can see exactly what's happening
        key_bits = 0
        for i in range(3, 8):
            key_bits |= data[i] << ((i - 3) * 8)

        # Find all set bits
        current = set()
        for bit in range(40):
            if key_bits & (1 << bit):
                name = KEY_MAP.get(bit, f"UNKNOWN_BIT_{bit}")
                current.add(name)

        pressed = current - prev
        released = prev - current
        if pressed:
            print(f"  Pressed: {pressed}  (raw bytes: {[hex(b) for b in data]})")
        if released:
            print(f"  Released: {released}")
        prev = current
    time.sleep(0.01)

g13.close()
print("Done")
PYEOF
