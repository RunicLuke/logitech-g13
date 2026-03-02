"""
G13 Macro Recorder

Captures keyboard and mouse input from /dev/input/ devices using evdev.
Records sequences of key presses, mouse clicks, movement, and scroll,
then serializes them as macro strings compatible with the G13 binding format.
"""

import time
import threading
import evdev
from evdev import ecodes


# Map evdev key codes back to our KEY_CODES names
EVDEV_TO_NAME = {
    1: "ESC", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7",
    9: "8", 10: "9", 11: "0", 12: "MINUS", 13: "EQUAL", 14: "BACKSPACE",
    15: "TAB", 16: "Q", 17: "W", 18: "E", 19: "R", 20: "T", 21: "Y",
    22: "U", 23: "I", 24: "O", 25: "P", 26: "LEFTBRACE", 27: "RIGHTBRACE",
    28: "ENTER", 29: "LEFTCTRL", 30: "A", 31: "S", 32: "D", 33: "F",
    34: "G", 35: "H", 36: "J", 37: "K", 38: "L", 39: "SEMICOLON",
    40: "APOSTROPHE", 41: "GRAVE", 42: "LEFTSHIFT", 43: "BACKSLASH",
    44: "Z", 45: "X", 46: "C", 47: "V", 48: "B", 49: "N", 50: "M",
    51: "COMMA", 52: "DOT", 53: "SLASH", 54: "RIGHTSHIFT", 56: "LEFTALT",
    57: "SPACE", 58: "CAPSLOCK",
    59: "F1", 60: "F2", 61: "F3", 62: "F4", 63: "F5", 64: "F6",
    65: "F7", 66: "F8", 67: "F9", 68: "F10", 87: "F11", 88: "F12",
    97: "RIGHTCTRL", 100: "RIGHTALT",
    102: "HOME", 103: "UP", 104: "PAGEUP", 105: "LEFT",
    106: "RIGHT", 107: "END", 108: "DOWN", 109: "PAGEDOWN",
    110: "INSERT", 111: "DELETE", 119: "PAUSE",
    113: "MUTE", 114: "VOLUMEDOWN", 115: "VOLUMEUP",
    125: "LEFTMETA", 126: "RIGHTMETA",
    163: "NEXTSONG", 164: "PLAYPAUSE", 165: "PREVIOUSSONG",
}

# Mouse button codes
MOUSE_BUTTONS = {
    ecodes.BTN_LEFT: "MOUSE_LEFT",
    ecodes.BTN_RIGHT: "MOUSE_RIGHT",
    ecodes.BTN_MIDDLE: "MOUSE_MIDDLE",
}


class RecordedEvent:
    """A single recorded input event."""
    def __init__(self, event_type, data, timestamp):
        self.event_type = event_type  # "key", "mouse_btn", "mouse_move", "scroll"
        self.data = data
        self.timestamp = timestamp


class MacroRecorder:
    """
    Records keyboard and mouse input from real input devices.

    Usage:
        recorder = MacroRecorder()
        recorder.start()
        # ... user types/clicks ...
        macro_string = recorder.stop()
    """

    def __init__(self, exclude_device_names=None):
        self.recording = False
        self.events = []
        self._threads = []
        self._stop_event = threading.Event()
        # Exclude our own virtual device and the G13 itself from recording
        self._exclude = set(exclude_device_names or [
            "G13 Virtual Keyboard",
            "G13",
            "Logitech G13",
        ])

    def _find_input_devices(self):
        """Find all keyboard and mouse input devices (excluding our virtual one)."""
        devices = []
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                if dev.name in self._exclude:
                    dev.close()
                    continue

                caps = dev.capabilities(verbose=False)
                has_keys = ecodes.EV_KEY in caps
                has_rel = ecodes.EV_REL in caps

                if has_keys or has_rel:
                    devices.append(dev)
                else:
                    dev.close()
            except Exception:
                continue

        return devices

    def start(self):
        """Start recording input from all keyboard/mouse devices."""
        self.recording = True
        self.events = []
        self._stop_event.clear()
        self._threads = []

        devices = self._find_input_devices()
        if not devices:
            print("Warning: No input devices found for recording")
            return

        for dev in devices:
            t = threading.Thread(target=self._record_device, args=(dev,), daemon=True)
            t.start()
            self._threads.append(t)

        print(f"Recording from {len(devices)} input device(s)...")

    def _record_device(self, dev):
        """Record events from a single input device."""
        try:
            # Accumulate mouse movement between syncs
            move_dx = 0
            move_dy = 0
            last_move_time = 0

            for event in dev.read_loop():
                if self._stop_event.is_set():
                    break

                if event.type == ecodes.EV_KEY:
                    name = EVDEV_TO_NAME.get(event.code)
                    mouse_btn = MOUSE_BUTTONS.get(event.code)

                    if name and event.value in (1, 0):  # press or release
                        action = "press" if event.value == 1 else "release"
                        self.events.append(RecordedEvent(
                            "key", {"name": name, "action": action},
                            event.timestamp()
                        ))
                    elif mouse_btn and event.value in (1, 0):
                        action = "press" if event.value == 1 else "release"
                        self.events.append(RecordedEvent(
                            "mouse_btn", {"button": mouse_btn, "action": action},
                            event.timestamp()
                        ))

                elif event.type == ecodes.EV_REL:
                    if event.code == ecodes.REL_X:
                        move_dx += event.value
                    elif event.code == ecodes.REL_Y:
                        move_dy += event.value
                    elif event.code == ecodes.REL_WHEEL:
                        self.events.append(RecordedEvent(
                            "scroll", {"amount": event.value},
                            event.timestamp()
                        ))
                    last_move_time = event.timestamp()

                elif event.type == ecodes.EV_SYN:
                    # Flush accumulated mouse movement
                    if move_dx != 0 or move_dy != 0:
                        self.events.append(RecordedEvent(
                            "mouse_move", {"dx": move_dx, "dy": move_dy},
                            last_move_time
                        ))
                        move_dx = 0
                        move_dy = 0

        except Exception as e:
            if not self._stop_event.is_set():
                print(f"Recording error on {dev.name}: {e}")
        finally:
            dev.close()

    def stop(self):
        """Stop recording and return the macro string."""
        self.recording = False
        self._stop_event.set()

        # Wait for threads to finish
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads = []

        if not self.events:
            return ""

        return self._events_to_macro()

    def _events_to_macro(self):
        """Convert recorded events to a macro string."""
        # Sort events by timestamp
        self.events.sort(key=lambda e: e.timestamp)

        steps = []
        held_keys = set()
        last_time = self.events[0].timestamp if self.events else 0

        for event in self.events:
            # Add delay if significant gap (> 50ms)
            gap_ms = int((event.timestamp - last_time) * 1000)
            if gap_ms > 50 and steps:
                # Round to nearest 50ms to keep macros clean
                delay = max(50, (gap_ms // 50) * 50)
                if delay <= 5000:  # Cap at 5 seconds
                    steps.append(f"DELAY:{delay}")

            if event.event_type == "key":
                name = event.data["name"]
                action = event.data["action"]

                if action == "press":
                    held_keys.add(name)
                elif action == "release":
                    if name in held_keys:
                        held_keys.discard(name)

                        # Check if this was part of a combo (modifier + key)
                        # We'll handle this by detecting combo patterns
                        steps.append(f"KEY:{name}")

            elif event.event_type == "mouse_btn":
                button = event.data["button"]
                action = event.data["action"]
                if action == "press":
                    steps.append(f"CLICK:{button}")

            elif event.event_type == "mouse_move":
                dx = event.data["dx"]
                dy = event.data["dy"]
                steps.append(f"MOVE:{dx},{dy}")

            elif event.event_type == "scroll":
                amount = event.data["amount"]
                steps.append(f"SCROLL:{amount}")

            last_time = event.timestamp

        # Post-process: detect combos and typed text
        return self._optimize_steps(steps)

    def _optimize_steps(self, steps):
        """
        Optimize raw key steps into higher-level actions.
        Detect modifier+key combos and consecutive character typing.
        """
        optimized = []
        i = 0

        while i < len(steps):
            step = steps[i]

            if step.startswith("KEY:"):
                key = step[4:]
                # Try to detect text typing (sequences of single characters)
                text_run = self._try_extract_text(steps, i)
                if text_run:
                    text, consumed = text_run
                    optimized.append(f"TYPE:{text}")
                    i += consumed
                    continue
                else:
                    # Single key tap
                    optimized.append(f"COMBO:{key}")

            elif step.startswith("CLICK:") or step.startswith("MOVE:") or step.startswith("SCROLL:"):
                optimized.append(step)
            elif step.startswith("DELAY:"):
                optimized.append(step)

            i += 1

        return ",".join(optimized)

    def _try_extract_text(self, steps, start):
        """Try to extract a run of typed text from consecutive KEY: steps."""
        KEY_TO_CHAR = {
            "A": "a", "B": "b", "C": "c", "D": "d", "E": "e", "F": "f",
            "G": "g", "H": "h", "I": "i", "J": "j", "K": "k", "L": "l",
            "M": "m", "N": "n", "O": "o", "P": "p", "Q": "q", "R": "r",
            "S": "s", "T": "t", "U": "u", "V": "v", "W": "w", "X": "x",
            "Y": "y", "Z": "z",
            "1": "1", "2": "2", "3": "3", "4": "4", "5": "5",
            "6": "6", "7": "7", "8": "8", "9": "9", "0": "0",
            "SPACE": " ", "ENTER": "\\n", "TAB": "\\t",
            "MINUS": "-", "EQUAL": "=", "DOT": ".", "COMMA": ",",
            "SLASH": "/", "BACKSLASH": "\\\\", "SEMICOLON": ";",
            "APOSTROPHE": "'", "GRAVE": "`",
            "LEFTBRACE": "[", "RIGHTBRACE": "]",
        }

        text = ""
        consumed = 0

        for j in range(start, len(steps)):
            step = steps[j]
            if step.startswith("KEY:"):
                key = step[4:]
                char = KEY_TO_CHAR.get(key)
                if char:
                    text += char
                    consumed += 1
                else:
                    break
            elif step.startswith("DELAY:"):
                # Small delays within typing are normal, skip them
                ms = int(step[6:])
                if ms <= 200:
                    consumed += 1
                else:
                    break
            else:
                break

        if len(text) >= 2:
            return text, consumed
        return None
