"""
Logitech G13 Key Mapping & uinput Emitter

Maps G13 keys to keyboard/mouse events and emits them via /dev/uinput.
Supports: single keys, key combos, typed text, shell commands, and multi-step macros.
"""

import os
import struct
import fcntl
import time
import threading


# Linux input event constants
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02

SYN_REPORT = 0x00

REL_X = 0x00
REL_Y = 0x01
REL_WHEEL = 0x08

# ioctl numbers
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_RELBIT = 0x40045566
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_DEV_SETUP = 0x405C5503

# Common key codes
KEY_CODES = {
    "ESC": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8,
    "8": 9, "9": 10, "0": 11, "MINUS": 12, "EQUAL": 13, "BACKSPACE": 14,
    "TAB": 15, "Q": 16, "W": 17, "E": 18, "R": 19, "T": 20, "Y": 21,
    "U": 22, "I": 23, "O": 24, "P": 25, "LEFTBRACE": 26, "RIGHTBRACE": 27,
    "ENTER": 28, "LEFTCTRL": 29, "A": 30, "S": 31, "D": 32, "F": 33,
    "G": 34, "H": 35, "J": 36, "K": 37, "L": 38, "SEMICOLON": 39,
    "APOSTROPHE": 40, "GRAVE": 41, "LEFTSHIFT": 42, "BACKSLASH": 43,
    "Z": 44, "X": 45, "C": 46, "V": 47, "B": 48, "N": 49, "M": 50,
    "COMMA": 51, "DOT": 52, "SLASH": 53, "RIGHTSHIFT": 54, "LEFTALT": 56,
    "SPACE": 57, "CAPSLOCK": 58, "F1": 59, "F2": 60, "F3": 61, "F4": 62,
    "F5": 63, "F6": 64, "F7": 65, "F8": 66, "F9": 67, "F10": 68,
    "F11": 87, "F12": 88, "UP": 103, "LEFT": 105, "RIGHT": 106, "DOWN": 108,
    "PAGEUP": 104, "PAGEDOWN": 109, "HOME": 102, "END": 107,
    "INSERT": 110, "DELETE": 111, "PAUSE": 119,
    "LEFTMETA": 125, "RIGHTMETA": 126, "RIGHTCTRL": 97, "RIGHTALT": 100,
    "VOLUMEUP": 115, "VOLUMEDOWN": 114, "MUTE": 113,
    "PLAYPAUSE": 164, "NEXTSONG": 163, "PREVIOUSSONG": 165,
    # Mouse buttons (for macro playback)
    "MOUSE_LEFT": 272, "MOUSE_RIGHT": 273, "MOUSE_MIDDLE": 274,
}

# Character to (key_code, needs_shift) mapping for TYPE: support
CHAR_MAP = {}
# Lowercase letters
for c in "abcdefghijklmnopqrstuvwxyz":
    CHAR_MAP[c] = (KEY_CODES[c.upper()], False)
# Uppercase letters
for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    CHAR_MAP[c] = (KEY_CODES[c], True)
# Numbers
for c in "1234567890":
    CHAR_MAP[c] = (KEY_CODES[c], False)
# Symbols (US keyboard layout)
CHAR_MAP.update({
    " ": (KEY_CODES["SPACE"], False),
    "\n": (KEY_CODES["ENTER"], False),
    "\t": (KEY_CODES["TAB"], False),
    "-": (KEY_CODES["MINUS"], False),
    "=": (KEY_CODES["EQUAL"], False),
    "[": (KEY_CODES["LEFTBRACE"], False),
    "]": (KEY_CODES["RIGHTBRACE"], False),
    ";": (KEY_CODES["SEMICOLON"], False),
    "'": (KEY_CODES["APOSTROPHE"], False),
    "`": (KEY_CODES["GRAVE"], False),
    "\\": (KEY_CODES["BACKSLASH"], False),
    ",": (KEY_CODES["COMMA"], False),
    ".": (KEY_CODES["DOT"], False),
    "/": (KEY_CODES["SLASH"], False),
    # Shifted symbols
    "!": (KEY_CODES["1"], True),
    "@": (KEY_CODES["2"], True),
    "#": (KEY_CODES["3"], True),
    "$": (KEY_CODES["4"], True),
    "%": (KEY_CODES["5"], True),
    "^": (KEY_CODES["6"], True),
    "&": (KEY_CODES["7"], True),
    "*": (KEY_CODES["8"], True),
    "(": (KEY_CODES["9"], True),
    ")": (KEY_CODES["0"], True),
    "_": (KEY_CODES["MINUS"], True),
    "+": (KEY_CODES["EQUAL"], True),
    "{": (KEY_CODES["LEFTBRACE"], True),
    "}": (KEY_CODES["RIGHTBRACE"], True),
    ":": (KEY_CODES["SEMICOLON"], True),
    '"': (KEY_CODES["APOSTROPHE"], True),
    "~": (KEY_CODES["GRAVE"], True),
    "|": (KEY_CODES["BACKSLASH"], True),
    "<": (KEY_CODES["COMMA"], True),
    ">": (KEY_CODES["DOT"], True),
    "?": (KEY_CODES["SLASH"], True),
})

# Default key mappings: G13 key name -> keyboard key name
DEFAULT_BINDINGS = {
    "G1": "ESC",
    "G2": "1",
    "G3": "2",
    "G4": "3",
    "G5": "4",
    "G6": "5",
    "G7": "TAB",
    "G8": "Q",
    "G9": "W",
    "G10": "E",
    "G11": "R",
    "G12": "T",
    "G13": "CAPSLOCK",
    "G14": "A",
    "G15": "S",
    "G16": "D",
    "G17": "F",
    "G18": "G",
    "G19": "LEFTSHIFT",
    "G20": "Z",
    "G21": "X",
    "G22": "C",
    "LEFT": "LEFT",
    "DOWN": "DOWN",
    "TOP": "UP",
    "BD": "SPACE",
}


class UInputDevice:
    """Emits keyboard and mouse events via /dev/uinput."""

    def __init__(self, name="G13 Virtual Keyboard"):
        self.fd = None
        self.name = name

    def open(self):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)

        # Enable key events
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        for code in KEY_CODES.values():
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)

        # Enable relative mouse events (for joystick)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
        fcntl.ioctl(self.fd, UI_SET_RELBIT, REL_X)
        fcntl.ioctl(self.fd, UI_SET_RELBIT, REL_Y)
        fcntl.ioctl(self.fd, UI_SET_RELBIT, REL_WHEEL)

        # Setup device identity
        name_bytes = self.name.encode("utf-8")[:79].ljust(80, b"\x00")
        setup = struct.pack("<HHHH", 0x03, 0x046D, 0xC21C, 1)
        setup += name_bytes
        setup += struct.pack("<I", 0)
        fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)

        # Create the device
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        time.sleep(0.5)

        return self

    def close(self):
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, UI_DEV_DESTROY)
            except Exception:
                pass
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *args):
        self.close()

    def _write_event(self, ev_type, code, value):
        t = time.time()
        sec = int(t)
        usec = int((t - sec) * 1000000)
        event = struct.pack("<QQHHi", sec, usec, ev_type, code, value)
        os.write(self.fd, event)

    def _syn(self):
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def key_press(self, key_name):
        """Press a key (key down)."""
        code = KEY_CODES.get(key_name.upper())
        if code is None:
            return
        self._write_event(EV_KEY, code, 1)
        self._syn()

    def key_release(self, key_name):
        """Release a key (key up)."""
        code = KEY_CODES.get(key_name.upper())
        if code is None:
            return
        self._write_event(EV_KEY, code, 0)
        self._syn()

    def key_tap(self, key_name):
        """Press and release a key."""
        self.key_press(key_name)
        time.sleep(0.01)
        self.key_release(key_name)

    def type_char(self, char):
        """Type a single character using the appropriate key + shift."""
        entry = CHAR_MAP.get(char)
        if entry is None:
            return
        code, needs_shift = entry
        if needs_shift:
            self._write_event(EV_KEY, KEY_CODES["LEFTSHIFT"], 1)
            self._syn()
        self._write_event(EV_KEY, code, 1)
        self._syn()
        time.sleep(0.005)
        self._write_event(EV_KEY, code, 0)
        self._syn()
        if needs_shift:
            self._write_event(EV_KEY, KEY_CODES["LEFTSHIFT"], 0)
            self._syn()
        time.sleep(0.005)

    def type_string(self, text):
        """Type a string character by character."""
        # Handle escape sequences
        text = text.replace("\\n", "\n").replace("\\t", "\t")
        for char in text:
            self.type_char(char)

    def combo_press(self, key_names):
        """Press multiple keys simultaneously, then release all."""
        codes = []
        for name in key_names:
            code = KEY_CODES.get(name.upper())
            if code is not None:
                codes.append(code)
        # Press all
        for code in codes:
            self._write_event(EV_KEY, code, 1)
        self._syn()
        time.sleep(0.02)
        # Release all (reverse order)
        for code in reversed(codes):
            self._write_event(EV_KEY, code, 0)
        self._syn()

    def move_mouse(self, dx, dy):
        """Move mouse by relative amount."""
        if dx != 0:
            self._write_event(EV_REL, REL_X, dx)
        if dy != 0:
            self._write_event(EV_REL, REL_Y, dy)
        if dx != 0 or dy != 0:
            self._syn()

    def scroll(self, amount):
        """Scroll wheel (positive = up, negative = down)."""
        self._write_event(EV_REL, REL_WHEEL, amount)
        self._syn()


def execute_binding(uinput, binding):
    """
    Execute a binding action. Supports:
    - "KEY"               -> single key press+release
    - "TYPE:text"         -> type text string
    - "COMBO:K1+K2"       -> simultaneous key combo
    - "CMD:command"       -> shell command
    - "KEY:keyname"       -> single key tap (from recorder)
    - "CLICK:button"      -> mouse click
    - "MOVE:dx,dy"        -> mouse move
    - "SCROLL:amount"     -> scroll wheel
    - "MACRO:step1,step2,..."  -> multi-step macro
    """
    if binding.startswith("TYPE:"):
        text = binding[5:]
        uinput.type_string(text)

    elif binding.startswith("COMBO:"):
        keys = binding[6:].split("+")
        uinput.combo_press(keys)

    elif binding.startswith("CMD:"):
        cmd = binding[4:]
        os.system(cmd + " &")

    elif binding.startswith("KEY:"):
        key = binding[4:]
        uinput.key_tap(key)

    elif binding.startswith("CLICK:"):
        button = binding[6:]
        code = KEY_CODES.get(button)
        if code:
            uinput._write_event(EV_KEY, code, 1)
            uinput._syn()
            time.sleep(0.02)
            uinput._write_event(EV_KEY, code, 0)
            uinput._syn()

    elif binding.startswith("MOVE:"):
        parts = binding[5:].split(",")
        if len(parts) == 2:
            dx, dy = int(parts[0]), int(parts[1])
            uinput.move_mouse(dx, dy)

    elif binding.startswith("SCROLL:"):
        amount = int(binding[7:])
        uinput.scroll(amount)

    elif binding.startswith("MACRO:"):
        steps = _parse_macro(binding[6:])
        for step in steps:
            if step.startswith("DELAY:"):
                ms = int(step[6:])
                time.sleep(ms / 1000.0)
            else:
                execute_binding(uinput, step)

    else:
        # Simple key tap
        uinput.key_tap(binding)


def _parse_macro(macro_str):
    """
    Parse a macro string into steps.
    Handles nested colons by tracking COMBO:/TYPE:/CMD:/DELAY: prefixes.
    Example: "COMBO:LEFTCTRL+S,DELAY:200,TYPE:npm run build\\n"
    """
    steps = []
    current = ""
    i = 0
    while i < len(macro_str):
        if macro_str[i] == "," and not _in_value(current):
            if current:
                steps.append(current)
            current = ""
        else:
            current += macro_str[i]
        i += 1
    if current:
        steps.append(current)
    return steps


def _in_value(s):
    """Check if we're inside a TYPE: value (which may contain commas in the text)."""
    # If the current buffer starts with TYPE: we're in a text value
    # and commas are part of the text until we see a known prefix after a comma
    return False  # Simple split on comma for now; TYPE values shouldn't contain commas


class KeyMapper:
    """Maps G13 key events to uinput keyboard/mouse events."""

    def __init__(self, uinput, bindings=None, joystick_mode="mouse",
                 joystick_sensitivity=5, joystick_deadzone=20):
        self.uinput = uinput
        self.bindings = bindings or DEFAULT_BINDINGS
        self.joystick_mode = joystick_mode
        self.joystick_sensitivity = joystick_sensitivity
        self.joystick_deadzone = joystick_deadzone
        self._joy_keys_held = set()
        self._held_simple_keys = {}  # g13_key -> binding for keys being held

    def handle_key_press(self, g13_key):
        """Handle a G13 key press."""
        binding = self.bindings.get(g13_key)
        if binding is None:
            return

        # For simple keys, do press-and-hold. For macros/type/combo, fire once.
        if self._is_simple_key(binding):
            self._held_simple_keys[g13_key] = binding
            self.uinput.key_press(binding)
        else:
            # Execute macro/type/combo/cmd in a thread to not block the main loop
            t = threading.Thread(target=execute_binding, args=(self.uinput, binding), daemon=True)
            t.start()

    def handle_key_release(self, g13_key):
        """Handle a G13 key release."""
        # Only release simple held keys
        binding = self._held_simple_keys.pop(g13_key, None)
        if binding is not None:
            self.uinput.key_release(binding)

    def _is_simple_key(self, binding):
        """Check if a binding is a simple key (not a macro/type/combo/cmd)."""
        return (
            not binding.startswith("TYPE:")
            and not binding.startswith("COMBO:")
            and not binding.startswith("CMD:")
            and not binding.startswith("MACRO:")
            and binding.upper() in KEY_CODES
        )

    def handle_joystick(self, x, y):
        """Handle joystick position (0-255, center ~128)."""
        cx = x - 128
        cy = y - 128

        if self.joystick_mode == "mouse":
            if abs(cx) > self.joystick_deadzone or abs(cy) > self.joystick_deadzone:
                dx = int(cx * self.joystick_sensitivity / 128)
                dy = int(cy * self.joystick_sensitivity / 128)
                self.uinput.move_mouse(dx, dy)

        elif self.joystick_mode == "scroll":
            if abs(cy) > self.joystick_deadzone:
                amount = -1 if cy > 0 else 1  # Inverted: push down = scroll down
                self.uinput.scroll(amount)

        elif self.joystick_mode == "arrows":
            new_keys = set()
            if cy < -self.joystick_deadzone:
                new_keys.add("UP")
            elif cy > self.joystick_deadzone:
                new_keys.add("DOWN")
            if cx < -self.joystick_deadzone:
                new_keys.add("LEFT")
            elif cx > self.joystick_deadzone:
                new_keys.add("RIGHT")

            for k in self._joy_keys_held - new_keys:
                self.uinput.key_release(k)
            for k in new_keys - self._joy_keys_held:
                self.uinput.key_press(k)
            self._joy_keys_held = new_keys
