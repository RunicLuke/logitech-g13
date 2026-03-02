"""
G13 On-Device Menu System

Provides a navigable menu on the G13 LCD, controlled by L1-L4 buttons.
BD (hold) opens/closes the menu. L1=Up, L2=Down, L3=Select, L4=Back.
"""

import json
import os
import time
import subprocess

from g13.lcd import (
    render_menu_list, render_rgb_editor, render_value_editor,
    render_char_editor, render_alarm_editor, render_timer, render_text,
)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


class MenuScreen:
    """Base class for all menu screens."""

    def handle_button(self, button):
        """Handle L1-L4 press. Returns a MenuAction or None."""
        return None

    def get_frame(self):
        """Render current state to LCD frame bytes."""
        return render_text("Menu", font_size=12)


class MenuAction:
    """Returned by handle_button to signal navigation."""
    NONE = "none"
    BACK = "back"
    OPEN = "open"       # open a sub-screen
    CLOSE = "close"     # close entire menu
    SAVE = "save"       # save config changes
    RESTART = "restart" # restart daemon

    def __init__(self, action=None, screen=None, save_data=None):
        self.action = action or self.NONE
        self.screen = screen        # for OPEN
        self.save_data = save_data  # dict of config changes for SAVE


class ListMenu(MenuScreen):
    """A scrollable list of items with a cursor."""

    def __init__(self, title, items):
        """items: list of (label, callback_or_screen_factory)"""
        self.title = title
        self.items = items
        self.selected = 0

    def handle_button(self, button):
        if button == "L1":  # Up
            self.selected = max(0, self.selected - 1)
        elif button == "L2":  # Down
            self.selected = min(len(self.items) - 1, self.selected + 1)
        elif button == "L3":  # Select
            if self.items:
                _, factory = self.items[self.selected]
                if callable(factory):
                    result = factory()
                    if isinstance(result, MenuScreen):
                        return MenuAction(MenuAction.OPEN, screen=result)
                    elif isinstance(result, MenuAction):
                        return result
        elif button == "L4":  # Back
            return MenuAction(MenuAction.BACK)
        return None

    def get_frame(self):
        labels = [item[0] for item in self.items]
        return render_menu_list(self.title, labels, self.selected)


class RGBEditor(MenuScreen):
    """Edit R, G, B values for a profile color."""

    def __init__(self, profile_key, profile_name, color):
        self.profile_key = profile_key
        self.profile_name = profile_name
        self.r = color.get("r", 0)
        self.g = color.get("g", 0)
        self.b = color.get("b", 0)
        self.channel = 0  # 0=R, 1=G, 2=B
        self.step = 15

    def handle_button(self, button):
        if button == "L1":  # Increase value
            if self.channel == 0:
                self.r = min(255, self.r + self.step)
            elif self.channel == 1:
                self.g = min(255, self.g + self.step)
            else:
                self.b = min(255, self.b + self.step)
        elif button == "L2":  # Decrease value
            if self.channel == 0:
                self.r = max(0, self.r - self.step)
            elif self.channel == 1:
                self.g = max(0, self.g - self.step)
            else:
                self.b = max(0, self.b - self.step)
        elif button == "L3":  # Next channel
            self.channel = (self.channel + 1) % 3
        elif button == "L4":  # Back / save
            return MenuAction(MenuAction.SAVE, save_data={
                "type": "profile_color",
                "profile": self.profile_key,
                "color": {"r": self.r, "g": self.g, "b": self.b},
            })
        return None

    def get_frame(self):
        return render_rgb_editor(
            f"{self.profile_name} Color",
            self.r, self.g, self.b, self.channel,
        )


class ValueEditor(MenuScreen):
    """Edit a single numeric value with up/down."""

    def __init__(self, label, value, min_val, max_val, step=1, save_key=None):
        self.label = label
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.save_key = save_key

    def handle_button(self, button):
        if button == "L1":
            self.value = min(self.max_val, self.value + self.step)
        elif button == "L2":
            self.value = max(self.min_val, self.value - self.step)
        elif button == "L4":  # Back / save
            if self.save_key:
                return MenuAction(MenuAction.SAVE, save_data={
                    "type": "value",
                    "key": self.save_key,
                    "value": self.value,
                })
            return MenuAction(MenuAction.BACK)
        return None

    def get_frame(self):
        return render_value_editor(self.label, self.value, self.min_val, self.max_val)


class CycleEditor(MenuScreen):
    """Cycle through a list of options."""

    def __init__(self, label, options, current_idx=0, save_key=None):
        self.label = label
        self.options = options
        self.idx = current_idx
        self.save_key = save_key

    def handle_button(self, button):
        if button == "L1":
            self.idx = (self.idx - 1) % len(self.options)
        elif button == "L2":
            self.idx = (self.idx + 1) % len(self.options)
        elif button == "L3":  # Confirm
            if self.save_key:
                return MenuAction(MenuAction.SAVE, save_data={
                    "type": "value",
                    "key": self.save_key,
                    "value": self.options[self.idx],
                })
            return MenuAction(MenuAction.BACK)
        elif button == "L4":
            return MenuAction(MenuAction.BACK)
        return None

    def get_frame(self):
        val = self.options[self.idx]
        return render_value_editor(self.label, val, None, None, is_text=True)


class CharEditor(MenuScreen):
    """Character-by-character text editor for LCD messages."""

    CHARSET = (
        " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        "0123456789!@#$%^&*()-_=+[]{}|;:',.<>?/~`\""
    )

    def __init__(self, current_text="", save_key=None):
        self.text = list(current_text)
        self.cursor = len(self.text)  # Position in text
        self.char_idx = 0  # Position in CHARSET
        self.save_key = save_key
        self.done = False

    def handle_button(self, button):
        if button == "L1":  # Scroll character up
            self.char_idx = (self.char_idx + 1) % len(self.CHARSET)
        elif button == "L2":  # Scroll character down
            self.char_idx = (self.char_idx - 1) % len(self.CHARSET)
        elif button == "L3":  # Insert character at cursor
            ch = self.CHARSET[self.char_idx]
            if self.cursor <= len(self.text):
                self.text.insert(self.cursor, ch)
                self.cursor += 1
        elif button == "L4":  # Delete last char or save if empty
            if self.cursor > 0:
                self.cursor -= 1
                self.text.pop(self.cursor)
            else:
                # Save and go back
                text = "".join(self.text)
                if self.save_key:
                    return MenuAction(MenuAction.SAVE, save_data={
                        "type": "value",
                        "key": self.save_key,
                        "value": text,
                    })
                return MenuAction(MenuAction.BACK)
        return None

    def get_frame(self):
        text = "".join(self.text)
        current_char = self.CHARSET[self.char_idx]
        return render_char_editor(text, self.cursor, current_char)


class AlarmEditor(MenuScreen):
    """Edit a single alarm: time, enabled, actions."""

    FIELDS = ["enabled", "hour", "minute", "flash", "display", "command"]

    def __init__(self, alarm_idx, alarm_data):
        self.alarm_idx = alarm_idx
        self.enabled = alarm_data.get("enabled", False)
        time_str = alarm_data.get("time", "00:00")
        parts = time_str.split(":") if time_str else ["00", "00"]
        self.hour = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
        self.minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        self.actions = list(alarm_data.get("actions", ["display"]))
        self.message = alarm_data.get("message", "")
        self.command = alarm_data.get("command", "")
        self.field_idx = 0  # Which field is selected

    def handle_button(self, button):
        field = self.FIELDS[self.field_idx]
        if button == "L3":  # Next field
            self.field_idx = (self.field_idx + 1) % len(self.FIELDS)
        elif button == "L1":  # Increase / toggle
            if field == "enabled":
                self.enabled = not self.enabled
            elif field == "hour":
                self.hour = (self.hour + 1) % 24
            elif field == "minute":
                self.minute = (self.minute + 5) % 60
            elif field in ("flash", "display", "command"):
                if field in self.actions:
                    self.actions.remove(field)
                else:
                    self.actions.append(field)
        elif button == "L2":  # Decrease / toggle
            if field == "enabled":
                self.enabled = not self.enabled
            elif field == "hour":
                self.hour = (self.hour - 1) % 24
            elif field == "minute":
                self.minute = (self.minute - 5) % 60
            elif field in ("flash", "display", "command"):
                if field in self.actions:
                    self.actions.remove(field)
                else:
                    self.actions.append(field)
        elif button == "L4":  # Save and go back
            return MenuAction(MenuAction.SAVE, save_data={
                "type": "alarm",
                "index": self.alarm_idx,
                "alarm": {
                    "time": f"{self.hour:02d}:{self.minute:02d}",
                    "enabled": self.enabled,
                    "actions": self.actions,
                    "message": self.message,
                    "command": self.command,
                },
            })
        return None

    def get_frame(self):
        return render_alarm_editor({
            "enabled": self.enabled,
            "hour": self.hour,
            "minute": self.minute,
            "actions": self.actions,
            "field_idx": self.field_idx,
            "fields": self.FIELDS,
        })


class AlarmMessageEditor(MenuScreen):
    """Use CharEditor to edit alarm message, then return to alarm."""

    def __init__(self, alarm_editor):
        self.alarm_editor = alarm_editor
        self.char_editor = CharEditor(alarm_editor.message)

    def handle_button(self, button):
        result = self.char_editor.handle_button(button)
        if result and result.action == MenuAction.BACK:
            self.alarm_editor.message = "".join(self.char_editor.text)
            return MenuAction(MenuAction.BACK)
        return None

    def get_frame(self):
        return self.char_editor.get_frame()


class TimerScreen(MenuScreen):
    """Countdown timer."""

    def __init__(self):
        self.duration_minutes = 5
        self.running = False
        self.end_time = 0
        self.finished = False

    def handle_button(self, button):
        if not self.running and not self.finished:
            if button == "L1":
                self.duration_minutes = min(99, self.duration_minutes + 1)
            elif button == "L2":
                self.duration_minutes = max(1, self.duration_minutes - 1)
            elif button == "L3":  # Start
                self.running = True
                self.end_time = time.time() + self.duration_minutes * 60
            elif button == "L4":
                return MenuAction(MenuAction.BACK)
        elif self.running:
            if button == "L3" or button == "L4":  # Stop
                self.running = False
                self.finished = False
        elif self.finished:
            if button:  # Any button dismisses
                self.finished = False
                self.running = False
                return MenuAction(MenuAction.BACK)
        return None

    def tick(self):
        """Called by daemon each loop. Returns True if timer just finished."""
        if self.running:
            remaining = self.end_time - time.time()
            if remaining <= 0:
                self.running = False
                self.finished = True
                return True
        return False

    def get_frame(self):
        if self.running:
            remaining = max(0, self.end_time - time.time())
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            time_str = f"{mins:02d}:{secs:02d}"
            return render_timer("Countdown", time_str, True)
        elif self.finished:
            return render_timer("TIME'S UP!", "00:00", False)
        else:
            return render_timer(
                "Set Minutes",
                f"{self.duration_minutes:02d}:00",
                False,
                hint="L1/L2:Adj L3:Start",
            )


class StopwatchScreen(MenuScreen):
    """Simple stopwatch."""

    def __init__(self):
        self.running = False
        self.start_time = 0
        self.elapsed = 0  # Accumulated seconds

    def handle_button(self, button):
        if button == "L3":  # Toggle start/stop
            if self.running:
                self.elapsed += time.time() - self.start_time
                self.running = False
            else:
                self.start_time = time.time()
                self.running = True
        elif button == "L4":
            if self.running:
                self.running = False
            elif self.elapsed > 0:
                self.elapsed = 0  # Reset
            else:
                return MenuAction(MenuAction.BACK)
        return None

    def get_frame(self):
        total = self.elapsed
        if self.running:
            total += time.time() - self.start_time
        mins = int(total // 60)
        secs = int(total % 60)
        tenths = int((total * 10) % 10)
        time_str = f"{mins:02d}:{secs:02d}.{tenths}"
        hint = "L3:Stop" if self.running else "L3:Start L4:Reset"
        return render_timer("Stopwatch", time_str, self.running, hint=hint)


class MenuSystem:
    """Top-level menu controller. Manages a stack of menu screens."""

    def __init__(self, config):
        self.active = False
        self.config = config
        self.stack = []  # Stack of MenuScreen objects
        self._pending_save = None  # Pending config save data
        # Timer/stopwatch instances (persist across menu open/close)
        self.timer = TimerScreen()
        self.stopwatch = StopwatchScreen()

    @property
    def is_active(self):
        return self.active

    def open(self):
        """Open the menu."""
        self.active = True
        self.stack = [self._build_main_menu()]

    def close(self):
        """Close the menu."""
        self.active = False
        self.stack = []

    def toggle(self):
        if self.active:
            self.close()
        else:
            self.open()

    def handle_button(self, button):
        """Process a button press. Returns MenuAction or None."""
        if not self.stack:
            return None

        screen = self.stack[-1]
        result = screen.handle_button(button)

        if result is None:
            return None

        if result.action == MenuAction.BACK:
            self.stack.pop()
            if not self.stack:
                self.close()
            return result

        if result.action == MenuAction.OPEN and result.screen:
            self.stack.append(result.screen)
            return result

        if result.action == MenuAction.SAVE:
            self._pending_save = result.save_data
            self.stack.pop()
            if not self.stack:
                self.close()
            return result

        if result.action == MenuAction.CLOSE:
            self.close()
            return result

        if result.action == MenuAction.RESTART:
            return result

        return result

    def get_frame(self):
        """Render the current menu screen."""
        if self.stack:
            return self.stack[-1].get_frame()
        return render_text("Menu", font_size=12)

    def get_pending_save(self):
        """Get and clear pending save data."""
        data = self._pending_save
        self._pending_save = None
        return data

    def tick(self):
        """Called each loop iteration. Returns 'timer_done' if countdown finished."""
        if self.timer.tick():
            return "timer_done"
        return None

    # --- Menu builders ---

    def _build_main_menu(self):
        return ListMenu("Main Menu", [
            ("RGB Settings", self._build_rgb_menu),
            ("Display", self._build_display_menu),
            ("Alarms", self._build_alarm_menu),
            ("Timer", self._build_timer_menu),
            ("Quick Actions", self._build_quick_menu),
        ])

    def _build_rgb_menu(self):
        profiles = self.config.get("profiles", {})
        items = []
        for key in ("M1", "M2", "M3"):
            profile = profiles.get(key, {})
            name = profile.get("name", key)
            color = profile.get("color", {"r": 0, "g": 0, "b": 0})
            items.append((f"{key}: {name}", self._rgb_factory(key, name, color)))
        return ListMenu("RGB Settings", items)

    def _rgb_factory(self, key, name, color):
        def factory():
            return RGBEditor(key, name, dict(color))
        return factory

    def _build_display_menu(self):
        return ListMenu("Display", [
            ("LCD Mode", self._lcd_mode_editor),
            ("Set Message", self._message_editor),
            ("Brightness", self._brightness_editor),
        ])

    def _lcd_mode_editor(self):
        modes = ["clock", "stats", "message"]
        current = self.config.get("lcd_mode", "clock")
        try:
            idx = modes.index(current)
        except ValueError:
            idx = 0
        return CycleEditor("LCD Mode", modes, idx, save_key="lcd_mode")

    def _message_editor(self):
        return CharEditor(self.config.get("lcd_message", ""), save_key="lcd_message")

    def _brightness_editor(self):
        # Brightness as percentage (10-100)
        current = int(self.config.get("brightness", 1.0) * 100)
        return ValueEditor("Brightness %", current, 10, 100, step=10, save_key="brightness_pct")

    def _build_alarm_menu(self):
        alarms = self.config.get("alarms", [
            {"time": "", "enabled": False, "actions": ["display"], "message": "", "command": ""},
            {"time": "", "enabled": False, "actions": ["display"], "message": "", "command": ""},
            {"time": "", "enabled": False, "actions": ["display"], "message": "", "command": ""},
        ])
        items = []
        for i, alarm in enumerate(alarms[:3]):
            t = alarm.get("time", "--:--")
            enabled = "ON" if alarm.get("enabled") else "OFF"
            label = f"Alarm {i+1}: {t} [{enabled}]"
            items.append((label, self._alarm_factory(i, alarm)))
        return ListMenu("Alarms", items)

    def _alarm_factory(self, idx, alarm):
        def factory():
            return AlarmEditor(idx, dict(alarm))
        return factory

    def _build_timer_menu(self):
        return ListMenu("Timer", [
            ("Countdown", lambda: self.timer),
            ("Stopwatch", lambda: self.stopwatch),
        ])

    def _build_quick_menu(self):
        return ListMenu("Quick Actions", [
            ("Cycle Color", lambda: MenuAction(MenuAction.SAVE, save_data={"type": "cycle_color"})),
            ("Stats Peek", lambda: MenuAction(MenuAction.SAVE, save_data={"type": "stats_peek"})),
            ("Restart Daemon", lambda: MenuAction(MenuAction.RESTART)),
        ])
