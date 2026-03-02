# Logitech G13 Linux Driver

A complete Linux userspace driver for the **Logitech G13 Advanced Gameboard**, built in Python for Raspberry Pi (and other Linux systems). Features full key remapping, LCD display control, RGB backlight management, macro recording, an on-device menu system, configurable alarms, and a web-based control panel.

## Features

### Key Remapping
- **22 programmable G-keys** (G1-G22) with per-profile bindings
- **3 profiles** (M1, M2, M3) with independent bindings, names, and RGB colors
- **Joystick** configurable as mouse, arrow keys, or scroll wheel
- **Binding types:**
  - Single key press (with hold support)
  - Type text strings (with `\n` and `\t` escapes)
  - Key combos (`Ctrl+Shift+P`, etc.)
  - Shell commands
  - Multi-step macros with delays

### Macro Recording
- Press **MR** to enter recording mode
- Select a G-key target, perform actions, press the G-key again to save
- Records keyboard input, mouse clicks, movement, and scroll
- Automatically detects text typing patterns and optimizes

### LCD Display (160x43 Monochrome)
- **Clock** - Large time display with date
- **System stats** - CPU load, memory usage, temperature
- **Custom message** - Any text you want
- **Animations** - Scrolling text, Matrix rain, fade effects, progress bars, animated GIFs

### RGB Backlight
- Full RGB color control with brightness levels
- Per-profile colors that switch automatically
- 7 preset colors accessible via hardware buttons
- Independent brightness control (10% to 100%)

### On-Device Menu System
- Press **BD** (thumb button) to open/close the menu on the LCD
- Navigate with **L1** (up), **L2** (down), **L3** (select), **L4** (back)
- **Menu features:**
  - Adjust RGB color for each profile
  - Change LCD display mode and message
  - Set backlight brightness
  - Configure up to 3 alarms
  - Countdown timer and stopwatch
  - Quick actions (cycle colors, stats peek, restart daemon)
- When the menu is closed, L1-L4 retain their quick-access shortcuts (LCD mode cycle, brightness up/down, color cycle)

### Alarm System
- 3 configurable alarms with HH:MM scheduling
- Per-alarm actions (mix and match):
  - **Display** - Show message on LCD for 10 seconds
  - **Flash** - Flash backlight red for 10 seconds
  - **Command** - Run any shell command (play sounds, send notifications, etc.)
- Configure via on-device menu or web GUI

### Web Control Panel
- Modern React-based GUI accessible from any browser on your network
- Tabs for: Backlight, LCD, Keys, Joystick, Alarms
- Visual key grid layout matching the physical G13
- Full binding editor with all binding types
- GIF upload for LCD animations
- Real-time color picker and brightness slider

## Requirements

- **Hardware:** Logitech G13 Gameboard (USB, Vendor ID `046d`, Product ID `c21c`)
- **OS:** Linux (tested on Raspberry Pi OS / Debian)
- **Python:** 3.9+
- **Node.js:** 18+ (for the web GUI only)
- **System packages:** `python3-venv`, `libhidapi-hidraw0`

## Installation

### Quick Setup

```bash
git clone https://github.com/RunicLuke/logitech-g13.git
cd logitech-g13
sudo bash setup.sh
```

The setup script will:
1. Create a Python virtual environment and install dependencies (`hidapi`, `Pillow`, `evdev`)
2. Install udev rules for device access
3. Configure uinput permissions
4. Install a systemd service (`g13.service`)

### Manual Setup

```bash
# Create venv and install Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install hidapi Pillow evdev

# Install udev rules (allows non-root HID access)
sudo cp /dev/stdin /etc/udev/rules.d/91-g13.rules << 'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="046d", ATTR{idProduct}=="c21c", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c21c", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger

# Setup uinput for virtual keyboard
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf
sudo modprobe uinput
sudo chmod 666 /dev/uinput
```

### Web GUI Setup

```bash
cd web
npm install
npm run build
```

## Usage

### Starting the Daemon

```bash
bash start_daemon.sh
```

Or manually:

```bash
sudo venv/bin/python3 -m g13.daemon
```

The daemon must run with root privileges (USB HID + uinput access). It listens on:
- Unix socket: `/tmp/g13daemon.sock` (CLI commands)
- TCP port `3114` (web GUI communication)

### Starting the Web GUI

```bash
bash start_web.sh
```

Then open `http://<your-ip>:3113` in a browser. The web server runs on port 3113 and proxies commands to the daemon on port 3114.

### Using as a Systemd Service

```bash
sudo systemctl start g13      # Start
sudo systemctl stop g13       # Stop
sudo systemctl status g13     # Check status
sudo journalctl -u g13 -f     # View logs
```

### CLI Commands

```bash
# Display text on LCD
bash g13cmd.sh lcd "Hello World"

# Set backlight color (by name or RGB)
bash g13cmd.sh color red
bash g13cmd.sh color 255 128 0
bash g13cmd.sh color blue 50        # 50% brightness

# Set LCD display mode
bash g13cmd.sh mode clock
bash g13cmd.sh mode stats
bash g13cmd.sh mode message

# Start animations
bash g13cmd.sh animate scroll "Breaking news: G13 is awesome"
bash g13cmd.sh animate matrix
bash g13cmd.sh animate fade "Hello"
bash g13cmd.sh animate progress "Loading"
bash g13cmd.sh animate gif /path/to/animation.gif
bash g13cmd.sh animate stop

# Reload config after manual edits
bash g13cmd.sh reload
```

### Hardware Button Reference

| Button | Function |
|--------|----------|
| **G1-G22** | Programmable keys (bindings per profile) |
| **BD** (thumb) | Open/close on-device LCD menu |
| **L1** | Menu: Up / Quick: Cycle LCD mode |
| **L2** | Menu: Down / Quick: Brightness down |
| **L3** | Menu: Select / Quick: Brightness up |
| **L4** | Menu: Back / Quick: Cycle color preset |
| **M1, M2, M3** | Switch profiles |
| **MR** | Start/stop macro recording |
| **Light** | Toggle backlight on/off |

## Configuration

All settings are stored in `config.json` in the project root. The file is updated automatically by the daemon (menu changes), web GUI, and CLI.

### Structure

```json
{
  "backlight": { "r": 0, "g": 100, "b": 255 },
  "lcd_mode": "clock",
  "lcd_message": "G13 Ready",
  "joystick_mode": "mouse",
  "joystick_sensitivity": 5,
  "joystick_deadzone": 20,
  "active_profile": "M1",
  "profiles": {
    "M1": {
      "name": "Gaming",
      "color": { "r": 0, "g": 100, "b": 255 },
      "bindings": {
        "G1": "ESC",
        "G2": "COMBO:LEFTCTRL+S",
        "G3": "TYPE:git status\n",
        "G4": "CMD:notify-send hello",
        "G5": "MACRO:COMBO:LEFTCTRL+S,DELAY:200,TYPE:npm run build\n"
      }
    }
  },
  "alarms": [
    { "time": "07:00", "enabled": true, "actions": ["flash", "display"], "message": "Wake up!", "command": "" }
  ]
}
```

### Binding Format Reference

| Prefix | Example | Description |
|--------|---------|-------------|
| *(none)* | `"SPACE"` | Single key (held while G-key is held) |
| `TYPE:` | `"TYPE:hello\n"` | Type text character by character |
| `COMBO:` | `"COMBO:LEFTCTRL+S"` | Press keys simultaneously |
| `CMD:` | `"CMD:firefox"` | Run a shell command |
| `MACRO:` | `"MACRO:TYPE:hi,DELAY:500,COMBO:LEFTCTRL+S"` | Multi-step sequence |

## Project Structure

```
├── g13/                     # Python package
│   ├── device.py            # USB HID interface
│   ├── keys.py              # Key mapping and uinput emulation
│   ├── lcd.py               # LCD rendering and animations
│   ├── menu.py              # On-device LCD menu system
│   ├── daemon.py            # Main event loop
│   ├── cli.py               # Command-line interface
│   └── recorder.py          # Macro recording
├── web/                     # Web control panel
│   ├── server.js            # Express.js backend
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── ColorPicker.jsx
│   │       ├── LcdControl.jsx
│   │       ├── KeyBindings.jsx
│   │       ├── JoystickConfig.jsx
│   │       └── AlarmConfig.jsx
│   └── package.json
├── config.json              # All settings and profiles
├── setup.sh                 # Automated setup script
├── start_daemon.sh          # Start the daemon
├── start_web.sh             # Start the web GUI
├── g13cmd.sh                # CLI wrapper
└── test_*.sh                # Hardware test scripts
```

## Test Scripts

These scripts test individual hardware features without the full daemon:

```bash
bash test_lcd.sh                    # Display test message on LCD
bash test_clock.sh                  # Show clock on LCD
bash test_stats.sh                  # Show system stats on LCD
bash test_color.sh red              # Set backlight to red
bash test_color.sh 0 255 128 50     # Set RGB at 50% brightness
bash test_keys.sh                   # Read key presses for 10 seconds
bash test_mr.sh                     # Test MR button detection
bash test_toprow.sh                 # Identify top-row button mappings
```

## Troubleshooting

**"Device not found" error:**
- Make sure the G13 is plugged in via USB
- Check with `lsusb | grep 046d:c21c`
- Try running with `sudo`
- Re-run `sudo bash setup.sh` to install udev rules

**Keys not working:**
- The daemon must be running (`bash start_daemon.sh`)
- Check that `/dev/uinput` exists and is writable
- Run `sudo modprobe uinput`

**LCD not updating:**
- Restart the daemon
- Try a direct test: `bash test_lcd.sh`

**Web GUI not loading:**
- Make sure you ran `npm install` and `npm run build` in the `web/` directory
- Check that port 3113 isn't blocked by a firewall
- The daemon must also be running for controls to work

## License

MIT
