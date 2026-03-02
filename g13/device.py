"""
Logitech G13 USB HID Device Driver

Handles low-level USB communication with the G13:
- Opening/closing the device
- Reading key/joystick state reports
- Sending LCD framebuffer data
- Setting backlight RGB color
"""

import hid
import struct
import time


VENDOR_ID = 0x046D
PRODUCT_ID = 0xC21C

# LCD dimensions
LCD_WIDTH = 160
LCD_HEIGHT = 43
LCD_BPP = 1
LCD_FRAME_SIZE = LCD_WIDTH * LCD_HEIGHT // 8  # 860 bytes

# Report IDs / commands
LCD_REPORT_SIZE = 992  # 32-byte header + 960 data (860 used + padding)

# G13 key names mapped to bit positions in the key report
# The key state is in bytes 3-6 of the 8-byte report (little-endian bitmask)
KEY_MAP = {
    # Byte 3 (report[3])
    0:  "G1",
    1:  "G2",
    2:  "G3",
    3:  "G4",
    4:  "G5",
    5:  "G6",
    6:  "G7",
    7:  "G8",
    # Byte 4 (report[4])
    8:  "G9",
    9:  "G10",
    10: "G11",
    11: "G12",
    12: "G13",
    13: "G14",
    14: "G15",
    15: "G16",
    # Byte 5 (report[5])
    16: "G17",
    17: "G18",
    18: "G19",
    19: "G20",
    20: "G21",
    21: "G22",
    22: "UNDEF1",
    23: "LIGHT_STATE",
    # Byte 6 (report[6])
    24: "BD",
    25: "L1",
    26: "L2",
    27: "L3",
    28: "L4",
    29: "M1",
    30: "M2",
    31: "M3",
    # Byte 7 (report[7])
    32: "MR",
    33: "LEFT",
    34: "DOWN",
    35: "TOP",
    36: "UNDEF3",
    37: "LIGHT_KEY1",
    38: "LIGHT_KEY2",
    39: "MISC_TOGGLE",
}

# Keys to ignore (noisy status bits, not real key presses)
IGNORED_KEYS = {"LIGHT_STATE", "MISC_TOGGLE", "LIGHT_KEY1", "LIGHT_KEY2", "UNDEF1", "UNDEF3"}


class G13Device:
    """Low-level interface to the Logitech G13 via HID."""

    def __init__(self):
        self.dev = None
        self._prev_keys = set()

    def open(self):
        """Open the G13 HID device."""
        self.dev = hid.device()
        self.dev.open(VENDOR_ID, PRODUCT_ID)
        self.dev.set_nonblocking(True)
        return self

    def close(self):
        """Close the HID device."""
        if self.dev:
            self.dev.close()
            self.dev = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *args):
        self.close()

    def set_color(self, r, g, b, brightness=1.0):
        """Set the key backlight color (0-255 per channel). Brightness 0.0-1.0."""
        r = int(r * brightness)
        g = int(g * brightness)
        b = int(b * brightness)
        # Report 7 = main key backlight + LCD backlight
        self.dev.send_feature_report([7, r, g, b, 0])

    def set_mkey_leds(self, m1=False, m2=False, m3=False, mr=False):
        """Set M-key indicator LEDs (red only, on/off). Shows which profile is active."""
        val = 0
        if m1: val |= 0x01
        if m2: val |= 0x02
        if m3: val |= 0x04
        if mr: val |= 0x08
        self.dev.send_feature_report([5, val, 0, 0, 0])

    def set_all_colors(self, r, g, b, brightness=1.0):
        """Set main backlight color."""
        self.set_color(r, g, b, brightness)

    def set_lcd(self, frame_bytes):
        """
        Send a framebuffer to the LCD.
        frame_bytes: 860 bytes, 1 bit per pixel, 160x43.
        """
        assert len(frame_bytes) == LCD_FRAME_SIZE, (
            f"Frame must be {LCD_FRAME_SIZE} bytes, got {len(frame_bytes)}"
        )
        # Build the 992-byte report:
        # Byte 0: report ID = 0x03
        # Bytes 1-31: header (zeros)
        # Bytes 32-891: pixel data (860 bytes)
        # Bytes 892-991: padding (zeros)
        report = bytearray(LCD_REPORT_SIZE)
        report[0] = 0x03
        report[32:32 + LCD_FRAME_SIZE] = frame_bytes
        self.dev.write(bytes(report))

    def read_keys(self, timeout_ms=10):
        """
        Read a key state report from the device.
        Returns (pressed_keys: set, joystick_x: int, joystick_y: int) or None if no data.
        """
        data = self.dev.read(8)
        if not data or len(data) < 8:
            return None

        # Parse joystick from bytes 1-2
        joy_x = data[1]
        joy_y = data[2]

        # Parse key bitmask from bytes 3-7
        key_bits = 0
        for i in range(3, 8):
            key_bits |= data[i] << ((i - 3) * 8)

        pressed = set()
        for bit, name in KEY_MAP.items():
            if key_bits & (1 << bit):
                if name not in IGNORED_KEYS:
                    pressed.add(name)

        return pressed, joy_x, joy_y

    def read_keys_diff(self, timeout_ms=10):
        """
        Read keys and return which were newly pressed and released.
        Returns (newly_pressed, newly_released, joystick_x, joystick_y) or None.
        """
        result = self.read_keys(timeout_ms)
        if result is None:
            return None

        pressed, joy_x, joy_y = result
        newly_pressed = pressed - self._prev_keys
        newly_released = self._prev_keys - pressed
        self._prev_keys = pressed

        return newly_pressed, newly_released, joy_x, joy_y


if __name__ == "__main__":
    print("Testing G13 device connection...")
    try:
        with G13Device() as g13:
            print("G13 opened successfully!")

            # Set color to blue
            g13.set_color(0, 0, 255)
            print("Set backlight to blue")

            # Read keys for a few seconds
            print("Reading keys for 5 seconds (press some G-keys)...")
            end = time.time() + 5
            while time.time() < end:
                result = g13.read_keys_diff()
                if result:
                    pressed, released, jx, jy = result
                    if pressed:
                        print(f"  Pressed: {pressed}")
                    if released:
                        print(f"  Released: {released}")
                    if jx != 128 or jy != 128:
                        print(f"  Joystick: ({jx}, {jy})")
                time.sleep(0.01)

            # Reset color to white
            g13.set_color(255, 255, 255)
            print("Done! Color reset to white.")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you have permissions. Try: sudo chmod 666 /dev/hidraw*")
        print("Or set up a udev rule (see setup.sh).")
