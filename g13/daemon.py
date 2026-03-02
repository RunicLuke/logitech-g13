"""
Logitech G13 Daemon

Main event loop that:
- Reads G13 key/joystick input and dispatches to key mapper
- Updates the LCD display periodically
- Listens on a Unix socket for CLI commands
"""

import json
import os
import signal
import socket
import select
import subprocess
import sys
import time
import threading

from g13.device import G13Device
from g13.lcd import (render_text, render_clock, render_system_stats,
                      ScrollingText, MatrixRain, GifPlayer, FadeText, ProgressBarAnim)
from g13.keys import UInputDevice, KeyMapper, DEFAULT_BINDINGS, KEY_CODES
from g13.recorder import MacroRecorder
from g13.menu import MenuSystem, MenuAction

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
SOCKET_PATH = "/tmp/g13daemon.sock"
TCP_PORT = 3114  # TCP socket for web GUI communication


def load_config():
    """Load configuration from config.json."""
    defaults = {
        "backlight": {"r": 0, "g": 100, "b": 255},
        "lcd_mode": "clock",
        "lcd_message": "G13 Ready",
        "joystick_mode": "mouse",
        "joystick_sensitivity": 5,
        "joystick_deadzone": 20,
        "active_profile": "M1",
        "profiles": {
            "M1": {"name": "Default", "bindings": DEFAULT_BINDINGS},
            "M2": {"name": "Profile 2", "bindings": {}},
            "M3": {"name": "Profile 3", "bindings": {}},
        },
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                user = json.load(f)
            defaults.update(user)
            # Backward compat: if "bindings" exists but no "profiles", migrate
            if "bindings" in user and "profiles" not in user:
                defaults["profiles"] = {
                    "M1": {"name": "Default", "bindings": user["bindings"]},
                    "M2": {"name": "Profile 2", "bindings": {}},
                    "M3": {"name": "Profile 3", "bindings": {}},
                }
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
    return defaults


def get_profile_bindings(config, profile_key):
    """Get the bindings for a specific profile."""
    profiles = config.get("profiles", {})
    profile = profiles.get(profile_key, {})
    return profile.get("bindings", {})


def get_profile_name(config, profile_key):
    """Get the display name for a profile."""
    profiles = config.get("profiles", {})
    profile = profiles.get(profile_key, {})
    return profile.get("name", profile_key)


COLOR_PRESETS = [
    ("blue", 0, 100, 255),
    ("red", 255, 0, 0),
    ("green", 0, 255, 0),
    ("purple", 128, 0, 255),
    ("cyan", 0, 255, 255),
    ("orange", 255, 128, 0),
    ("white", 255, 255, 255),
]

LCD_MODES = ["clock", "stats", "message"]

BRIGHTNESS_STEPS = [0.1, 0.25, 0.5, 0.75, 1.0]


class G13Daemon:
    def __init__(self):
        self.running = False
        self.config = load_config()
        self.g13 = None
        self.uinput = None
        self.mapper = None
        self.lcd_mode = self.config["lcd_mode"]
        self.lcd_message = self.config["lcd_message"]
        self.lcd_dirty = True
        self.last_lcd_update = 0
        self.sock = None
        self.tcp_sock = None
        # Hardware button state
        self.brightness = 1.0
        self.brightness_idx = len(BRIGHTNESS_STEPS) - 1
        self.color_idx = 0
        self.backlight_on = True
        self.light_btn_held = False
        # Animation state
        self.animation = None
        self.last_anim_frame = 0
        # Profile state
        self.active_profile = self.config.get("active_profile", "M1")
        # Macro recording state
        self.recorder = None
        self.recording_state = None  # None, "waiting_key", "recording"
        self.recording_target = None  # G-key to assign the macro to
        self._mr_last_press = 0  # Debounce timestamp
        # Menu system
        self.menu = MenuSystem(self.config)
        # Alarm system
        self._alarm_last_check = ""
        self._alarm_triggered = {}  # "HH:MM" -> True (cleared each minute)
        self._alarm_flash_until = 0
        self._alarm_flash_state = False
        self._alarm_display_until = 0
        self._alarm_display_msg = ""
        # Stats peek
        self._stats_peek_until = 0

    def start(self):
        """Start the daemon."""
        print("Starting G13 daemon...")

        # Open devices
        self.g13 = G13Device()
        self.g13.open()
        print("G13 device opened")

        self.uinput = UInputDevice()
        self.uinput.open()
        print("uinput device created")

        # Setup key mapper with active profile
        bindings = get_profile_bindings(self.config, self.active_profile)
        self.mapper = KeyMapper(
            self.uinput, bindings,
            joystick_mode=self.config["joystick_mode"],
            joystick_sensitivity=self.config["joystick_sensitivity"],
            joystick_deadzone=self.config["joystick_deadzone"],
        )

        # Set M-key LED for active profile
        self.g13.set_mkey_leds(
            m1=(self.active_profile == "M1"),
            m2=(self.active_profile == "M2"),
            m3=(self.active_profile == "M3"),
        )
        profile_name = get_profile_name(self.config, self.active_profile)
        print(f"Active profile: {self.active_profile} ({profile_name})")

        # Set initial backlight from active profile color (fall back to global backlight)
        profile = self.config.get("profiles", {}).get(self.active_profile, {})
        c = profile.get("color", self.config["backlight"])
        self.g13.set_all_colors(c["r"], c["g"], c["b"])
        print(f"Backlight set to ({c['r']}, {c['g']}, {c['b']}) [{self.active_profile}]")

        # Setup socket for CLI communication
        self._setup_socket()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.running = True
        print("G13 daemon running. Press Ctrl+C to stop.")
        self._main_loop()

    def _setup_socket(self):
        """Create Unix socket for CLI commands."""
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(SOCKET_PATH)
        self.sock.setblocking(False)
        os.chmod(SOCKET_PATH, 0o666)

        # TCP socket for web GUI
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_sock.bind(('127.0.0.1', TCP_PORT))
        self.tcp_sock.listen(5)
        self.tcp_sock.setblocking(False)
        print(f"TCP socket listening on port {TCP_PORT}")

    def _signal_handler(self, signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        self.running = False

    def _handle_command(self, data):
        """Process a command from the CLI."""
        try:
            cmd = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            return

        action = cmd.get("action")

        if action == "lcd":
            self.lcd_mode = "message"
            self.lcd_message = cmd.get("text", "")
            self.lcd_dirty = True

        elif action == "lcd_mode":
            self.lcd_mode = cmd.get("mode", "clock")
            self.lcd_dirty = True

        elif action == "color":
            r = cmd.get("r", 0)
            g = cmd.get("g", 0)
            b = cmd.get("b", 0)
            brightness = cmd.get("brightness", 1.0)
            self.g13.set_color(r, g, b, brightness)

        elif action == "reload":
            self.config = load_config()
            c = self.config["backlight"]
            self.g13.set_all_colors(c["r"], c["g"], c["b"], c.get("brightness", 1.0))
            # Reload bindings for current profile
            self.mapper.bindings = get_profile_bindings(self.config, self.active_profile)
            self.mapper.joystick_mode = self.config.get("joystick_mode", "mouse")
            self.mapper.joystick_sensitivity = self.config.get("joystick_sensitivity", 5)
            self.mapper.joystick_deadzone = self.config.get("joystick_deadzone", 20)
            self.lcd_mode = self.config["lcd_mode"]
            self.lcd_message = self.config.get("lcd_message", "")
            self.lcd_dirty = True
            print("Config reloaded")

        elif action == "profile":
            profile_key = cmd.get("profile", "M1")
            if profile_key in ("M1", "M2", "M3"):
                self._switch_profile(profile_key)

        elif action == "animate":
            anim_type = cmd.get("type", "scroll")
            if anim_type == "scroll":
                self.animation = ScrollingText(
                    cmd.get("text", "Hello G13!"),
                    font_size=cmd.get("font_size", 14),
                    fps=cmd.get("fps", 20),
                    loops=cmd.get("loops", 0),
                )
            elif anim_type == "matrix":
                self.animation = MatrixRain(fps=cmd.get("fps", 15))
            elif anim_type == "gif":
                path = cmd.get("path", "")
                if os.path.exists(path):
                    self.animation = GifPlayer(
                        path, fps=cmd.get("fps", 10), loops=cmd.get("loops", 0)
                    )
                else:
                    print(f"GIF not found: {path}")
            elif anim_type == "fade":
                self.animation = FadeText(
                    cmd.get("text", "G13"),
                    font_size=cmd.get("font_size", 14),
                    fps=cmd.get("fps", 15),
                    cycles=cmd.get("cycles", 3),
                )
            elif anim_type == "progress":
                self.animation = ProgressBarAnim(
                    label=cmd.get("text", "Loading"),
                    fps=cmd.get("fps", 20),
                    duration=cmd.get("duration", 5.0),
                )
            print(f"Animation started: {anim_type}")

        elif action == "animate_stop":
            self.animation = None
            self.lcd_dirty = True
            print("Animation stopped")

        elif action == "status":
            print(f"LCD mode: {self.lcd_mode}, animation: {self.animation is not None}")

    def _handle_hw_buttons(self, pressed, released):
        """Handle BD, L1-L4 and light button presses."""
        # --- BD press toggles menu ---
        if "BD" in pressed:
            self.menu.config = self.config  # Ensure menu has latest config
            self.menu.toggle()
            if self.menu.is_active:
                print("Menu opened")
            else:
                print("Menu closed")
                self.lcd_dirty = True

        # --- Menu active: route L1-L4 to menu ---
        if self.menu.is_active:
            for btn in ("L1", "L2", "L3", "L4"):
                if btn in pressed:
                    result = self.menu.handle_button(btn)
                    if result:
                        self._handle_menu_action(result)
            # Don't process L1-L4 shortcuts while menu is open
            # Still process MR, M1-M3, light button below
        else:
            # --- Normal L1-L4 shortcuts (menu closed) ---
            if "L1" in pressed:
                # Cycle LCD mode
                try:
                    idx = LCD_MODES.index(self.lcd_mode)
                except ValueError:
                    idx = -1
                self.lcd_mode = LCD_MODES[(idx + 1) % len(LCD_MODES)]
                self.lcd_dirty = True
                print(f"LCD mode: {self.lcd_mode}")

            if "L2" in pressed:
                # Brightness down
                if self.brightness_idx > 0:
                    self.brightness_idx -= 1
                    self.brightness = BRIGHTNESS_STEPS[self.brightness_idx]
                    self._apply_color()
                    print(f"Brightness: {int(self.brightness * 100)}%")

            if "L3" in pressed:
                # Brightness up
                if self.brightness_idx < len(BRIGHTNESS_STEPS) - 1:
                    self.brightness_idx += 1
                    self.brightness = BRIGHTNESS_STEPS[self.brightness_idx]
                    self._apply_color()
                    print(f"Brightness: {int(self.brightness * 100)}%")

            if "L4" in pressed:
                # Cycle color preset
                self.color_idx = (self.color_idx + 1) % len(COLOR_PRESETS)
                self._apply_color()
                name = COLOR_PRESETS[self.color_idx][0]
                print(f"Color: {name}")

        # MR button - macro recording (debounced - 1 second cooldown)
        if "MR" in pressed:
            now = time.time()
            if now - self._mr_last_press > 1.0:
                self._mr_last_press = now
                self._handle_mr_press()
            return  # Don't process other buttons during recording

        # If we're waiting for a G-key target, intercept it
        if self.recording_state == "waiting_key":
            for key in pressed:
                if key.startswith("G"):
                    self._start_recording(key)
                    return

        # If recording, pressing the target G-key again stops it
        if self.recording_state == "recording":
            if self.recording_target in pressed:
                self._stop_recording()
                return

        # M-key profile switching (only when not recording)
        if self.recording_state is None:
            for mkey in ("M1", "M2", "M3"):
                if mkey in pressed:
                    self._switch_profile(mkey)

        # Light button (both LIGHT_KEY1 and LIGHT_KEY2 fire together)
        if "LIGHT_KEY1" in pressed and not self.light_btn_held:
            self.light_btn_held = True
            self.backlight_on = not self.backlight_on
            if self.backlight_on:
                self._apply_color()
                print("Backlight ON")
            else:
                self.g13.set_all_colors(0, 0, 0)
                print("Backlight OFF")
        if "LIGHT_KEY1" in released:
            self.light_btn_held = False

    def _handle_mr_press(self):
        """Handle the MR button for macro recording."""
        if self.recording_state is None:
            # Start: enter "waiting for target key" mode
            self.recording_state = "waiting_key"
            self.animation = None
            frame = render_text("MACRO RECORD\n\nPress a G-key\nto assign to...", font_size=10)
            self.g13.set_lcd(frame)
            # Light up MR LED
            self.g13.set_mkey_leds(mr=True)
            print("Macro recording: waiting for target G-key")

        elif self.recording_state == "waiting_key":
            # Cancel recording
            self._cancel_recording()

        elif self.recording_state == "recording":
            # MR during recording also cancels
            self._cancel_recording()

    def _start_recording(self, target_key):
        """Start recording input to assign to target_key."""
        self.recording_target = target_key
        self.recording_state = "recording"
        self.recorder = MacroRecorder()
        self.recorder.start()

        frame = render_text(
            f"RECORDING {target_key}\n\nType/click now...\nPress {target_key} to stop",
            font_size=10
        )
        self.g13.set_lcd(frame)
        print(f"Recording macro for {target_key}...")

    def _stop_recording(self):
        """Stop recording and save the macro."""
        if not self.recorder:
            self._cancel_recording()
            return

        macro_string = self.recorder.stop()
        self.recorder = None

        if not macro_string:
            frame = render_text(f"No input recorded\n\nCancelled", font_size=10)
            self.g13.set_lcd(frame)
            print("Recording cancelled: no input captured")
        else:
            # Save to current profile
            target = self.recording_target
            binding = f"MACRO:{macro_string}"

            profiles = self.config.get("profiles", {})
            profile = profiles.get(self.active_profile, {})
            bindings = profile.get("bindings", {})
            bindings[target] = binding
            profile["bindings"] = bindings
            profiles[self.active_profile] = profile
            self.config["profiles"] = profiles

            # Update mapper
            self.mapper.bindings = bindings

            # Save to disk
            try:
                with open(CONFIG_PATH, "w") as f:
                    json.dump(self.config, f, indent=4)
            except Exception as e:
                print(f"Error saving config: {e}")

            # Show confirmation
            # Truncate for display
            display_macro = macro_string[:40] + ("..." if len(macro_string) > 40 else "")
            frame = render_text(
                f"Saved to {target}!\n\n{display_macro}",
                font_size=10
            )
            self.g13.set_lcd(frame)
            print(f"Macro saved to {target}: {macro_string[:80]}")

        self.recording_state = None
        self.recording_target = None
        # Restore M-key LED
        self.g13.set_mkey_leds(
            m1=(self.active_profile == "M1"),
            m2=(self.active_profile == "M2"),
            m3=(self.active_profile == "M3"),
        )
        self.lcd_dirty = True
        self.last_lcd_update = time.time() + 2  # Show confirmation for 2s

    def _cancel_recording(self):
        """Cancel macro recording."""
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        self.recording_state = None
        self.recording_target = None
        self.g13.set_mkey_leds(
            m1=(self.active_profile == "M1"),
            m2=(self.active_profile == "M2"),
            m3=(self.active_profile == "M3"),
        )
        frame = render_text("Recording\nCancelled", font_size=14)
        self.g13.set_lcd(frame)
        self.lcd_dirty = True
        self.last_lcd_update = time.time() + 1
        print("Macro recording cancelled")

    def _switch_profile(self, profile_key):
        """Switch to a different key binding profile."""
        self.active_profile = profile_key
        bindings = get_profile_bindings(self.config, profile_key)
        self.mapper.bindings = bindings
        self.g13.set_mkey_leds(
            m1=(profile_key == "M1"),
            m2=(profile_key == "M2"),
            m3=(profile_key == "M3"),
        )
        profile_name = get_profile_name(self.config, profile_key)
        print(f"Profile: {profile_key} ({profile_name})")

        # Apply profile color
        profile = self.config.get("profiles", {}).get(profile_key, {})
        color = profile.get("color")
        if color:
            self.g13.set_all_colors(color["r"], color["g"], color["b"], self.brightness)

        # Briefly show profile name on LCD
        self.animation = None
        frame = render_text(f"{profile_key}\n{profile_name}", font_size=16)
        try:
            self.g13.set_lcd(frame)
        except Exception:
            pass
        self.lcd_dirty = True
        self.last_lcd_update = time.time() + 1

    def _apply_color(self):
        """Apply the current color preset at current brightness."""
        if not self.backlight_on:
            return
        _, r, g, b = COLOR_PRESETS[self.color_idx]
        self.g13.set_all_colors(r, g, b, self.brightness)

    def _handle_menu_action(self, result):
        """Process a MenuAction returned by the menu system."""
        if result.action == MenuAction.SAVE:
            save_data = self.menu.get_pending_save()
            if save_data:
                self._apply_menu_save(save_data)

        elif result.action == MenuAction.RESTART:
            self.menu.close()
            print("Restart requested from menu")
            # Re-exec the daemon
            os.execv(sys.executable, [sys.executable, "-m", "g13.daemon"])

        elif result.action == MenuAction.CLOSE:
            self.lcd_dirty = True

        elif result.action == MenuAction.BACK:
            if not self.menu.is_active:
                self.lcd_dirty = True

    def _apply_menu_save(self, save_data):
        """Apply a config change from the menu and save to disk."""
        save_type = save_data.get("type")

        if save_type == "profile_color":
            profile_key = save_data["profile"]
            color = save_data["color"]
            profiles = self.config.get("profiles", {})
            profile = profiles.get(profile_key, {})
            profile["color"] = color
            profiles[profile_key] = profile
            self.config["profiles"] = profiles
            # Apply immediately if it's the active profile
            if profile_key == self.active_profile:
                self.g13.set_all_colors(color["r"], color["g"], color["b"], self.brightness)
            print(f"Saved {profile_key} color: {color}")

        elif save_type == "value":
            key = save_data["key"]
            value = save_data["value"]
            if key == "lcd_mode":
                self.lcd_mode = value
                self.config["lcd_mode"] = value
                self.lcd_dirty = True
            elif key == "lcd_message":
                self.lcd_message = value
                self.config["lcd_message"] = value
                self.lcd_dirty = True
            elif key == "brightness_pct":
                self.brightness = value / 100.0
                # Find closest brightness step
                closest = min(range(len(BRIGHTNESS_STEPS)),
                              key=lambda i: abs(BRIGHTNESS_STEPS[i] - self.brightness))
                self.brightness_idx = closest
                self.brightness = BRIGHTNESS_STEPS[closest]
                self._apply_color()
            else:
                self.config[key] = value
            print(f"Saved {key}: {value}")

        elif save_type == "alarm":
            idx = save_data["index"]
            alarm = save_data["alarm"]
            alarms = self.config.get("alarms", [{}, {}, {}])
            while len(alarms) <= idx:
                alarms.append({"time": "", "enabled": False, "actions": ["display"],
                               "message": "", "command": ""})
            alarms[idx] = alarm
            self.config["alarms"] = alarms
            print(f"Saved alarm {idx + 1}: {alarm}")

        elif save_type == "cycle_color":
            self.color_idx = (self.color_idx + 1) % len(COLOR_PRESETS)
            self._apply_color()
            name = COLOR_PRESETS[self.color_idx][0]
            print(f"Quick action: Color {name}")

        elif save_type == "stats_peek":
            self._stats_peek_until = time.time() + 5
            print("Quick action: Stats peek")

        # Save config to disk
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def _check_alarms(self):
        """Check if any alarms should trigger right now."""
        now_hm = time.strftime("%H:%M")

        # Clear triggered dict when minute changes
        if now_hm != self._alarm_last_check:
            self._alarm_triggered = {}
            self._alarm_last_check = now_hm

        alarms = self.config.get("alarms", [])
        for i, alarm in enumerate(alarms):
            if not alarm.get("enabled"):
                continue
            alarm_time = alarm.get("time", "")
            if alarm_time != now_hm:
                continue
            if self._alarm_triggered.get(i):
                continue

            # Trigger this alarm!
            self._alarm_triggered[i] = True
            actions = alarm.get("actions", ["display"])
            message = alarm.get("message", f"Alarm {i + 1}!")
            print(f"ALARM {i + 1} triggered: {alarm_time} - {message}")

            if "flash" in actions:
                self._alarm_flash_until = time.time() + 10
                self._alarm_flash_state = False

            if "display" in actions:
                self._alarm_display_until = time.time() + 10
                self._alarm_display_msg = message

            if "command" in actions:
                cmd = alarm.get("command", "")
                if cmd:
                    try:
                        subprocess.Popen(cmd, shell=True)
                        print(f"Alarm command: {cmd}")
                    except Exception as e:
                        print(f"Alarm command error: {e}")

    def _update_alarm_effects(self):
        """Update alarm flash and display effects."""
        now = time.time()

        # Flash backlight
        if now < self._alarm_flash_until:
            # Toggle between bright red and current color every 0.5s
            if int(now * 2) % 2 == 0:
                if not self._alarm_flash_state:
                    self.g13.set_all_colors(255, 0, 0, 1.0)
                    self._alarm_flash_state = True
            else:
                if self._alarm_flash_state:
                    self._apply_color()
                    self._alarm_flash_state = False
        elif self._alarm_flash_state:
            # Flash ended, restore color
            self._apply_color()
            self._alarm_flash_state = False

        # Display alarm message
        if now < self._alarm_display_until:
            frame = render_text(f"!! ALARM !!\n\n{self._alarm_display_msg}", font_size=12)
            self.g13.set_lcd(frame)
            return True  # Suppress normal LCD update
        return False

    def _update_animation(self):
        """Update LCD with the next animation frame."""
        now = time.time()
        if now - self.last_anim_frame < self.animation.frame_interval:
            return
        self.last_anim_frame = now

        frame = self.animation.next_frame()
        if frame is None:
            # Animation finished
            self.animation = None
            self.lcd_dirty = True
            print("Animation finished")
            return

        try:
            self.g13.set_lcd(frame)
        except Exception as e:
            print(f"Animation frame error: {e}")

    def _update_lcd(self):
        """Update the LCD display based on current mode."""
        now = time.time()
        interval = 1.0
        if not self.lcd_dirty and now - self.last_lcd_update < interval:
            return

        try:
            # Stats peek override
            if now < self._stats_peek_until:
                frame = render_system_stats()
            elif self.lcd_mode == "clock":
                frame = render_clock()
            elif self.lcd_mode == "stats":
                frame = render_system_stats()
            elif self.lcd_mode == "message":
                frame = render_text(self.lcd_message, font_size=12)
            else:
                frame = render_clock()

            self.g13.set_lcd(frame)
            self.last_lcd_update = now
            self.lcd_dirty = False
        except Exception as e:
            print(f"LCD update error: {e}")

    def _main_loop(self):
        """Main event loop."""
        try:
            while self.running:
                # Read keys
                result = self.g13.read_keys_diff()
                if result:
                    pressed, released, jx, jy = result
                    # Handle hardware buttons (BD, L1-L4, light button, MR, M1-M3)
                    self._handle_hw_buttons(pressed, released)
                    # Forward G-keys and bindable keys to key mapper (skip during recording)
                    if self.recording_state is None:
                        hw_only = {"M1", "M2", "M3", "MR", "L1", "L2", "L3", "L4", "BD"}
                        for key in pressed:
                            if key not in hw_only:
                                self.mapper.handle_key_press(key)
                        for key in released:
                            if key not in hw_only:
                                self.mapper.handle_key_release(key)
                    self.mapper.handle_joystick(jx, jy)

                # Check for CLI commands (Unix DGRAM)
                try:
                    data, _ = self.sock.recvfrom(4096)
                    self._handle_command(data)
                except BlockingIOError:
                    pass

                # Check for TCP connections (web GUI)
                try:
                    conn, addr = self.tcp_sock.accept()
                    data = conn.recv(4096)
                    if data:
                        self._handle_command(data)
                    conn.close()
                except BlockingIOError:
                    pass

                # Check alarms
                self._check_alarms()

                # Tick menu timer/stopwatch
                timer_event = self.menu.tick()
                if timer_event == "timer_done":
                    # Timer finished - flash and show message
                    self._alarm_flash_until = time.time() + 5
                    self._alarm_display_until = time.time() + 5
                    self._alarm_display_msg = "Timer Done!"
                    print("Countdown timer finished!")

                # Update LCD
                if self.recording_state is not None:
                    pass  # LCD is managed by the recorder flow
                elif self._update_alarm_effects():
                    pass  # Alarm display active
                elif self.menu.is_active:
                    # Render menu to LCD
                    try:
                        frame = self.menu.get_frame()
                        self.g13.set_lcd(frame)
                    except Exception as e:
                        print(f"Menu render error: {e}")
                elif self.animation:
                    self._update_animation()
                else:
                    self._update_lcd()

                # Small sleep to avoid busy-waiting
                time.sleep(0.005)

        finally:
            self.stop()

    def stop(self):
        """Clean shutdown."""
        self.running = False
        print("Shutting down...")

        if self.g13:
            try:
                # Show shutdown message
                frame = render_text("G13 Daemon\nStopped", font_size=14)
                self.g13.set_lcd(frame)
                self.g13.set_color(0, 0, 0)
            except Exception:
                pass
            self.g13.close()

        if self.uinput:
            self.uinput.close()

        if self.tcp_sock:
            self.tcp_sock.close()

        if self.sock:
            self.sock.close()
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

        print("G13 daemon stopped.")


def main():
    daemon = G13Daemon()
    daemon.start()


if __name__ == "__main__":
    main()
