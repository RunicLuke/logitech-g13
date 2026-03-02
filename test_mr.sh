#!/bin/bash
# Test MR button detection specifically
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
sudo venv/bin/python3 << 'PYEOF'
import time
from g13.device import G13Device, KEY_MAP, IGNORED_KEYS

g13 = G13Device()
g13.open()
g13.dev.set_nonblocking(True)

print("Press MR button a few times (10 seconds)...")
print("Showing ALL keys including ignored ones:")

prev = set()
end = time.time() + 10
while time.time() < end:
    data = g13.dev.read(8)
    if data and len(data) >= 8:
        key_bits = 0
        for i in range(3, 8):
            key_bits |= data[i] << ((i - 3) * 8)

        current = set()
        for bit in range(40):
            if key_bits & (1 << bit):
                name = KEY_MAP.get(bit, f"BIT_{bit}")
                current.add(name)

        pressed = current - prev
        released = prev - current
        if pressed:
            in_ignored = pressed & IGNORED_KEYS
            real = pressed - IGNORED_KEYS
            print(f"  Pressed: real={real} ignored={in_ignored}")
        prev = current
    time.sleep(0.01)

g13.close()
print("Done")
PYEOF
