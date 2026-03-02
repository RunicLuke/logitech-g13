"""
Logitech G13 CLI - Command-line interface for the G13 daemon.

Usage:
    python -m g13.cli lcd "Hello World"      Display text on LCD
    python -m g13.cli color 0 100 255         Set backlight RGB
    python -m g13.cli color red               Set backlight by name
    python -m g13.cli mode clock              LCD mode: clock/stats/message
    python -m g13.cli alarm                   Show alarm settings
    python -m g13.cli reload                  Reload config.json
    python -m g13.cli test                    Quick device test (no daemon needed)
"""

import json
import os
import socket
import sys

SOCKET_PATH = "/tmp/g13daemon.sock"

NAMED_COLORS = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "white": (255, 255, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "orange": (255, 128, 0),
    "purple": (128, 0, 255),
    "pink": (255, 64, 128),
    "off": (0, 0, 0),
}


def send_command(cmd):
    """Send a command to the daemon via Unix socket."""
    if not os.path.exists(SOCKET_PATH):
        print("Error: G13 daemon is not running.")
        print("Start it with: sudo python -m g13.daemon")
        sys.exit(1)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(cmd).encode("utf-8"), SOCKET_PATH)
    finally:
        sock.close()


def cmd_lcd(args):
    """Send text to the LCD display."""
    if not args:
        print("Usage: g13cli lcd <text>")
        return
    text = " ".join(args)
    send_command({"action": "lcd", "text": text})
    print(f"LCD: {text}")


def cmd_color(args):
    """Set backlight color."""
    if not args:
        print("Usage: g13cli color <name|r g b> [brightness%] [--zone all|main|mkeys]")
        print(f"Named colors: {', '.join(NAMED_COLORS.keys())}")
        print("Brightness: 0-100 (e.g. 'color red 50' for 50%)")
        print("Zones: all (default), main (G-keys+LCD), mkeys (M1-M5)")
        return

    # Parse zone flag
    zone = "all"
    filtered = []
    i = 0
    while i < len(args):
        if args[i] == "--zone" and i + 1 < len(args):
            zone = args[i + 1]
            i += 2
        else:
            filtered.append(args[i])
            i += 1
    args = filtered

    brightness = 1.0
    # Check if last arg is a brightness percentage
    if len(args) >= 2:
        try:
            maybe_bright = int(args[-1])
            if 0 <= maybe_bright <= 100 and (len(args) == 2 or len(args) == 4):
                brightness = maybe_bright / 100.0
                args = args[:-1]
        except ValueError:
            pass

    if len(args) == 1:
        name = args[0].lower()
        if name.startswith("#") and len(name) == 7:
            r = int(name[1:3], 16)
            g = int(name[3:5], 16)
            b = int(name[5:7], 16)
        elif name in NAMED_COLORS:
            r, g, b = NAMED_COLORS[name]
        else:
            print(f"Unknown color: {name}")
            print(f"Named colors: {', '.join(NAMED_COLORS.keys())}")
            return
    elif len(args) == 3:
        r, g, b = int(args[0]), int(args[1]), int(args[2])
    else:
        print("Usage: g13cli color <name|r g b> [brightness%] [--zone all|main|mkeys]")
        return

    send_command({"action": "color", "r": r, "g": g, "b": b, "brightness": brightness, "zone": zone})
    print(f"Color: ({r}, {g}, {b}) brightness={int(brightness*100)}% zone={zone}")


def cmd_mode(args):
    """Set LCD display mode."""
    if not args or args[0] not in ("clock", "stats", "message"):
        print("Usage: g13cli mode <clock|stats|message>")
        return
    send_command({"action": "lcd_mode", "mode": args[0]})
    print(f"LCD mode: {args[0]}")


def cmd_reload(args):
    """Reload configuration."""
    send_command({"action": "reload"})
    print("Config reloaded.")


def cmd_test(args):
    """Quick device test (no daemon needed)."""
    from g13.device import G13Device
    from g13.lcd import render_text
    import time

    print("Testing G13 device directly...")
    try:
        with G13Device() as g13:
            print("Device opened!")

            # Set color
            g13.set_color(0, 255, 0)
            print("Backlight: green")

            # Show text on LCD
            frame = render_text("G13 Test OK!\nPi 5 Driver\nAll systems go", font_size=12)
            g13.set_lcd(frame)
            print("LCD: test message displayed")

            # Read keys briefly
            print("Press G-keys for 3 seconds...")
            end = time.time() + 3
            while time.time() < end:
                result = g13.read_keys_diff()
                if result:
                    pressed, released, jx, jy = result
                    if pressed:
                        print(f"  Pressed: {pressed}")
                    if released:
                        print(f"  Released: {released}")
                time.sleep(0.01)

            g13.set_color(255, 255, 255)
            print("Test complete!")
    except Exception as e:
        print(f"Error: {e}")
        print("Try running with sudo, or set up udev rules (see setup.sh)")


def cmd_animate(args):
    """Start an LCD animation."""
    if not args:
        print("Usage:")
        print("  g13cli animate scroll <text>     Scrolling text")
        print("  g13cli animate matrix            Matrix rain effect")
        print("  g13cli animate fade <text>       Fade text in/out")
        print("  g13cli animate progress [label]  Progress bar")
        print("  g13cli animate gif <path>        Play animated GIF")
        print("  g13cli animate stop              Stop animation")
        return

    anim_type = args[0].lower()

    if anim_type == "stop":
        send_command({"action": "animate_stop"})
        print("Animation stopped")
    elif anim_type == "scroll":
        text = " ".join(args[1:]) if len(args) > 1 else "Hello G13!"
        send_command({"action": "animate", "type": "scroll", "text": text})
        print(f"Scrolling: {text}")
    elif anim_type == "matrix":
        send_command({"action": "animate", "type": "matrix"})
        print("Matrix rain started")
    elif anim_type == "fade":
        text = " ".join(args[1:]) if len(args) > 1 else "G13"
        send_command({"action": "animate", "type": "fade", "text": text})
        print(f"Fading: {text}")
    elif anim_type == "progress":
        label = " ".join(args[1:]) if len(args) > 1 else "Loading"
        send_command({"action": "animate", "type": "progress", "text": label})
        print(f"Progress bar: {label}")
    elif anim_type == "gif":
        if len(args) < 2:
            print("Usage: g13cli animate gif <path>")
            return
        path = os.path.abspath(args[1])
        send_command({"action": "animate", "type": "gif", "path": path})
        print(f"GIF: {path}")
    else:
        print(f"Unknown animation: {anim_type}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    commands = {
        "lcd": cmd_lcd,
        "color": cmd_color,
        "mode": cmd_mode,
        "animate": cmd_animate,
        "reload": cmd_reload,
        "test": cmd_test,
    }

    cmd = sys.argv[1].lower()
    if cmd in commands:
        commands[cmd](sys.argv[2:])
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
