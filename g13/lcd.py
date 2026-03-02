"""
Logitech G13 LCD Display Manager

Renders text and images to the G13's 160x43 monochrome LCD.
Uses Pillow to create images, then converts to the G13's bitmap format.
"""

import os
import time
import textwrap
from PIL import Image, ImageDraw, ImageFont

from g13.device import LCD_WIDTH, LCD_HEIGHT, LCD_FRAME_SIZE


# Try to find a good monospace font
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "/usr/share/fonts/truetype/noto/NotoMono-Regular.ttf",
]


def _find_font(size=10):
    """Find an available monospace font."""
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def image_to_frame(img):
    """
    Convert a PIL Image (160x43) to G13 LCD frame bytes.

    The G13 LCD uses a column-major, vertical-strip format:
    - Each byte represents 8 vertical pixels in a column
    - Data is organized in horizontal strips of 160 bytes
    - Each strip covers 8 rows of pixels
    - 5 full strips (40 rows) + 1 partial strip (3 rows) = 43 rows
    - Total: 160 * 5 + 60 = 860 bytes

    Within each byte, bit 0 = top pixel, bit 7 = bottom pixel.
    """
    if img.size != (LCD_WIDTH, LCD_HEIGHT):
        img = img.resize((LCD_WIDTH, LCD_HEIGHT))
    img = img.convert("1")  # 1-bit black and white

    pixels = img.load()
    frame = bytearray(LCD_FRAME_SIZE)

    for x in range(LCD_WIDTH):
        for y in range(LCD_HEIGHT):
            if pixels[x, y] == 0:  # Black pixel = "on" for the LCD
                strip = y // 8
                bit = y % 8
                byte_idx = strip * LCD_WIDTH + x
                if byte_idx < LCD_FRAME_SIZE:
                    frame[byte_idx] |= (1 << bit)

    return bytes(frame)


def render_text(text, font_size=10, invert=False):
    """
    Render text to a G13 LCD frame.
    Supports multi-line text and automatic word wrapping.
    Returns frame bytes ready to send to the device.
    """
    font = _find_font(font_size)
    img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)  # white background
    draw = ImageDraw.Draw(img)

    # Calculate chars per line based on font
    bbox = font.getbbox("M")
    char_width = bbox[2] - bbox[0]
    line_height = bbox[3] - bbox[1] + 2
    chars_per_line = LCD_WIDTH // max(char_width, 1)
    max_lines = LCD_HEIGHT // max(line_height, 1)

    # Word wrap
    lines = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width=chars_per_line)
        lines.extend(wrapped if wrapped else [""])

    lines = lines[:max_lines]

    # Draw text
    y = 0
    for line in lines:
        draw.text((0, y), line, font=font, fill=0)  # black text
        y += line_height

    if invert:
        from PIL import ImageOps
        img = ImageOps.invert(img.convert("L")).convert("1")

    return image_to_frame(img)


def render_clock():
    """Render current time and date to LCD frame."""
    now = time.strftime("%H:%M:%S")
    date = time.strftime("%Y-%m-%d")
    day = time.strftime("%A")

    font_big = _find_font(18)
    font_small = _find_font(10)

    img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
    draw = ImageDraw.Draw(img)

    # Time in large font, centered
    bbox = font_big.getbbox(now)
    tw = bbox[2] - bbox[0]
    draw.text(((LCD_WIDTH - tw) // 2, 0), now, font=font_big, fill=0)

    # Date and day below
    draw.text((0, 24), f"{date}  {day}", font=font_small, fill=0)

    return image_to_frame(img)


def render_system_stats():
    """Render CPU, memory, and temperature info to LCD frame."""
    import subprocess

    # CPU usage
    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()[0]
    except Exception:
        load = "?"

    # Memory
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = int(lines[0].split()[1]) // 1024
        available = int(lines[2].split()[1]) // 1024
        used = total - available
        mem = f"{used}/{total}MB"
    except Exception:
        mem = "?"

    # Temperature (Pi-specific)
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp = int(f.read().strip()) / 1000
        temp_str = f"{temp:.1f}C"
    except Exception:
        temp_str = "?"

    text = f"Load: {load}\nMem:  {mem}\nTemp: {temp_str}"
    return render_text(text, font_size=12)


###############################################################################
# Menu Rendering Functions
###############################################################################

def render_menu_list(title, items, selected_idx):
    """Render a scrollable list menu with a cursor.

    Shows title at top, up to 3 visible items with '>' cursor on selected.
    """
    font_title = _find_font(10)
    font_item = _find_font(10)

    img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
    draw = ImageDraw.Draw(img)

    # Title bar (inverted)
    draw.rectangle([0, 0, LCD_WIDTH, 12], fill=0)
    draw.text((2, 1), title[:26], font=font_title, fill=1)

    # Visible items (3 lines below title)
    visible = 3
    bbox = font_item.getbbox("M")
    line_h = bbox[3] - bbox[1] + 2

    # Scroll offset so selected item is always visible
    scroll = max(0, selected_idx - visible + 1)
    scroll = min(scroll, max(0, len(items) - visible))

    y = 14
    for i in range(scroll, min(scroll + visible, len(items))):
        prefix = "> " if i == selected_idx else "  "
        label = items[i]
        # Truncate long labels
        if len(prefix + label) > 26:
            label = label[:24] + ".."
        draw.text((0, y), prefix + label, font=font_item, fill=0)
        y += line_h

    # Scroll indicators
    if scroll > 0:
        draw.text((150, 14), "^", font=font_item, fill=0)
    if scroll + visible < len(items):
        draw.text((150, 14 + line_h * (visible - 1)), "v", font=font_item, fill=0)

    return image_to_frame(img)


def render_rgb_editor(label, r, g, b, active_channel):
    """Render RGB color editor with channel bars.

    active_channel: 0=R, 1=G, 2=B (shown with arrow indicator).
    """
    font = _find_font(9)
    img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
    draw = ImageDraw.Draw(img)

    # Title
    draw.rectangle([0, 0, LCD_WIDTH, 11], fill=0)
    draw.text((2, 1), label[:26], font=font, fill=1)

    channels = [("R", r), ("G", g), ("B", b)]
    bar_max = 100  # pixels wide
    y = 13

    for idx, (ch_name, val) in enumerate(channels):
        marker = ">" if idx == active_channel else " "
        draw.text((0, y), f"{marker}{ch_name}:", font=font, fill=0)

        # Bar background
        bar_x = 24
        bar_w = int(bar_max * val / 255)
        draw.rectangle([bar_x, y + 1, bar_x + bar_max, y + 8], outline=0)
        if bar_w > 0:
            draw.rectangle([bar_x, y + 1, bar_x + bar_w, y + 8], fill=0)

        # Value text
        draw.text((bar_x + bar_max + 4, y), f"{val}", font=font, fill=0)
        y += 10

    return image_to_frame(img)


def render_value_editor(label, value, min_val, max_val, is_text=False):
    """Render a value editor with the current value displayed large."""
    font_label = _find_font(10)
    font_value = _find_font(16)
    font_hint = _find_font(8)

    img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
    draw = ImageDraw.Draw(img)

    # Title
    draw.rectangle([0, 0, LCD_WIDTH, 12], fill=0)
    draw.text((2, 1), label[:26], font=font_label, fill=1)

    # Value centered
    val_str = str(value)
    bbox = font_value.getbbox(val_str)
    tw = bbox[2] - bbox[0]
    draw.text(((LCD_WIDTH - tw) // 2, 15), val_str, font=font_value, fill=0)

    # Hint
    if not is_text and min_val is not None:
        draw.text((2, 35), "L1:Up L2:Down L4:Save", font=font_hint, fill=0)
    else:
        draw.text((2, 35), "L1/L2:Cycle L3:OK L4:Back", font=font_hint, fill=0)

    return image_to_frame(img)


def render_char_editor(current_text, cursor_pos, current_char):
    """Render character-by-character text editor."""
    font = _find_font(10)
    font_small = _find_font(8)

    img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
    draw = ImageDraw.Draw(img)

    # Title bar
    draw.rectangle([0, 0, LCD_WIDTH, 11], fill=0)
    draw.text((2, 1), "Edit Message", font=font, fill=1)

    # Current text with cursor
    display_text = current_text[:20]
    if len(current_text) > 20:
        # Show last 20 chars around cursor
        start = max(0, cursor_pos - 18)
        display_text = current_text[start:start + 20]
    draw.text((2, 13), display_text, font=font, fill=0)

    # Cursor underline position
    bbox = font.getbbox("M")
    cw = bbox[2] - bbox[0]
    visible_cursor = min(cursor_pos, 19)
    cx = 2 + visible_cursor * cw
    draw.line([(cx, 24), (cx + cw, 24)], fill=0)

    # Current character selection
    draw.text((2, 26), f"Char: [{current_char}]", font=font, fill=0)

    # Hints
    draw.text((2, 36), "L1/2:Chr L3:Add L4:Del/Save", font=font_small, fill=0)

    return image_to_frame(img)


def render_alarm_editor(alarm_data):
    """Render alarm configuration screen.

    alarm_data: dict with enabled, hour, minute, actions, field_idx, fields
    """
    font = _find_font(9)
    font_small = _find_font(8)

    img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
    draw = ImageDraw.Draw(img)

    enabled = alarm_data["enabled"]
    hour = alarm_data["hour"]
    minute = alarm_data["minute"]
    actions = alarm_data.get("actions", [])
    field_idx = alarm_data.get("field_idx", 0)
    fields = alarm_data.get("fields", [])

    # Title
    draw.rectangle([0, 0, LCD_WIDTH, 11], fill=0)
    status = "ON" if enabled else "OFF"
    draw.text((2, 1), f"Alarm [{status}] {hour:02d}:{minute:02d}", font=font, fill=1)

    # Fields
    y = 13
    field_labels = {
        "enabled": f"Enabled: {'YES' if enabled else 'NO'}",
        "hour": f"Hour: {hour:02d}",
        "minute": f"Minute: {minute:02d}",
        "flash": f"Flash: {'ON' if 'flash' in actions else 'OFF'}",
        "display": f"Display: {'ON' if 'display' in actions else 'OFF'}",
        "command": f"Command: {'ON' if 'command' in actions else 'OFF'}",
    }

    # Show 3 fields at a time
    visible = 3
    scroll = max(0, field_idx - visible + 1)
    for i in range(scroll, min(scroll + visible, len(fields))):
        field = fields[i]
        marker = ">" if i == field_idx else " "
        text = field_labels.get(field, field)
        draw.text((0, y), f"{marker}{text}", font=font, fill=0)
        y += 10

    # Hint
    draw.text((0, 36), "L1/2:Adj L3:Next L4:Save", font=font_small, fill=0)

    return image_to_frame(img)


def render_timer(label, time_str, running, hint=None):
    """Render timer/stopwatch display."""
    font_label = _find_font(10)
    font_time = _find_font(18)
    font_hint = _find_font(8)

    img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
    draw = ImageDraw.Draw(img)

    # Title bar
    draw.rectangle([0, 0, LCD_WIDTH, 12], fill=0)
    indicator = " [RUN]" if running else ""
    draw.text((2, 1), f"{label}{indicator}", font=font_label, fill=1)

    # Time centered
    bbox = font_time.getbbox(time_str)
    tw = bbox[2] - bbox[0]
    draw.text(((LCD_WIDTH - tw) // 2, 14), time_str, font=font_time, fill=0)

    # Hint
    if hint:
        draw.text((2, 36), hint, font=font_hint, fill=0)
    elif not running:
        draw.text((2, 36), "L4:Back", font=font_hint, fill=0)

    return image_to_frame(img)


###############################################################################
# LCD Animation Classes
###############################################################################

class Animation:
    """Base class for LCD animations."""
    def __init__(self, fps=20):
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self.finished = False

    def next_frame(self):
        """Return the next frame as 860 bytes, or None if animation is done."""
        raise NotImplementedError


class ScrollingText(Animation):
    """Horizontally scrolling text for long messages."""
    def __init__(self, text, font_size=14, fps=20, loops=0):
        super().__init__(fps)
        self.font = _find_font(font_size)
        self.text = text
        self.loops = loops  # 0 = infinite
        self.loop_count = 0

        # Render the full text to get its width
        bbox = self.font.getbbox(text)
        self.text_width = bbox[2] - bbox[0] + 20  # padding
        self.text_height = bbox[3] - bbox[1]
        self.offset = 0
        self.total_scroll = self.text_width + LCD_WIDTH

    def next_frame(self):
        if self.finished:
            return None

        img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
        draw = ImageDraw.Draw(img)

        # Draw text at current offset, vertically centered
        y = (LCD_HEIGHT - self.text_height) // 2
        draw.text((LCD_WIDTH - self.offset, y), self.text, font=self.font, fill=0)

        self.offset += 2  # pixels per frame

        if self.offset > self.total_scroll:
            self.offset = 0
            self.loop_count += 1
            if self.loops > 0 and self.loop_count >= self.loops:
                self.finished = True

        return image_to_frame(img)


class MatrixRain(Animation):
    """Falling character effect (Matrix-style)."""
    def __init__(self, fps=15):
        super().__init__(fps)
        import random
        self.random = random
        self.font = _find_font(8)
        bbox = self.font.getbbox("M")
        self.char_w = bbox[2] - bbox[0]
        self.char_h = bbox[3] - bbox[1]
        self.cols = LCD_WIDTH // max(self.char_w, 1)
        self.rows = LCD_HEIGHT // max(self.char_h, 1)
        # Each column has a drop position and speed
        self.drops = [random.randint(-self.rows, 0) for _ in range(self.cols)]
        self.speeds = [random.choice([1, 1, 1, 2]) for _ in range(self.cols)]
        self.chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%"

    def next_frame(self):
        img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
        draw = ImageDraw.Draw(img)

        for col in range(self.cols):
            x = col * self.char_w
            drop = self.drops[col]

            # Draw a trail of characters
            for row in range(max(0, drop - 4), max(0, drop + 1)):
                if 0 <= row < self.rows:
                    ch = self.random.choice(self.chars)
                    y = row * self.char_h
                    draw.text((x, y), ch, font=self.font, fill=0)

            # Move drop down
            self.drops[col] += self.speeds[col]
            if self.drops[col] > self.rows + 5:
                self.drops[col] = self.random.randint(-5, -1)
                self.speeds[col] = self.random.choice([1, 1, 1, 2])

        return image_to_frame(img)


class GifPlayer(Animation):
    """Play an animated GIF on the LCD."""
    def __init__(self, path, fps=10, loops=0):
        super().__init__(fps)
        self.loops = loops  # 0 = infinite
        self.loop_count = 0
        self.frame_idx = 0

        # Pre-convert all GIF frames to LCD format
        gif = Image.open(path)
        self.frames = []
        try:
            while True:
                frame = gif.copy().resize((LCD_WIDTH, LCD_HEIGHT)).convert("1")
                self.frames.append(image_to_frame(frame))
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass

        if not self.frames:
            self.finished = True

    def next_frame(self):
        if self.finished or not self.frames:
            return None

        frame = self.frames[self.frame_idx]
        self.frame_idx += 1

        if self.frame_idx >= len(self.frames):
            self.frame_idx = 0
            self.loop_count += 1
            if self.loops > 0 and self.loop_count >= self.loops:
                self.finished = True

        return frame


class FadeText(Animation):
    """Fade text in and out using dithering."""
    def __init__(self, text, font_size=14, fps=15, cycles=3):
        super().__init__(fps)
        self.cycles = cycles
        self.cycle_count = 0
        self.step = 0
        self.total_steps = 20  # steps per fade in/out
        self.fading_in = True

        # Pre-render the text as a grayscale image
        self.font = _find_font(font_size)
        img = Image.new("L", (LCD_WIDTH, LCD_HEIGHT), color=255)
        draw = ImageDraw.Draw(img)
        bbox = self.font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (LCD_WIDTH - tw) // 2
        y = (LCD_HEIGHT - th) // 2
        draw.text((x, y), text, font=self.font, fill=0)
        self.text_img = img

    def next_frame(self):
        if self.finished:
            return None

        # Calculate alpha (0=invisible, 255=fully visible)
        if self.fading_in:
            alpha = int(255 * self.step / self.total_steps)
        else:
            alpha = int(255 * (self.total_steps - self.step) / self.total_steps)

        # Blend: white background with text at alpha
        blended = Image.blend(
            Image.new("L", (LCD_WIDTH, LCD_HEIGHT), 255),
            self.text_img,
            alpha / 255.0
        )
        # Dither to 1-bit
        result = blended.convert("1")

        self.step += 1
        if self.step > self.total_steps:
            self.step = 0
            if self.fading_in:
                self.fading_in = False
            else:
                self.fading_in = True
                self.cycle_count += 1
                if self.cycles > 0 and self.cycle_count >= self.cycles:
                    self.finished = True

        return image_to_frame(result)


class ProgressBarAnim(Animation):
    """Animated progress bar that fills up."""
    def __init__(self, label="Loading", fps=20, duration=5.0):
        super().__init__(fps)
        self.label = label
        self.total_frames = int(fps * duration)
        self.current_frame = 0
        self.font = _find_font(10)

    def next_frame(self):
        if self.current_frame >= self.total_frames:
            self.finished = True
            return None

        progress = self.current_frame / self.total_frames
        self.current_frame += 1

        img = Image.new("1", (LCD_WIDTH, LCD_HEIGHT), color=1)
        draw = ImageDraw.Draw(img)

        # Label
        draw.text((2, 2), self.label, font=self.font, fill=0)

        # Progress bar
        bar_y = 18
        bar_h = 12
        bar_margin = 4
        bar_max_w = LCD_WIDTH - bar_margin * 2

        # Outline
        draw.rectangle(
            [bar_margin, bar_y, bar_margin + bar_max_w, bar_y + bar_h],
            outline=0
        )
        # Fill
        fill_w = int(bar_max_w * progress)
        if fill_w > 0:
            draw.rectangle(
                [bar_margin + 1, bar_y + 1, bar_margin + fill_w, bar_y + bar_h - 1],
                fill=0
            )

        # Percentage
        pct_text = f"{int(progress * 100)}%"
        draw.text((bar_margin, bar_y + bar_h + 4), pct_text, font=self.font, fill=0)

        return image_to_frame(img)


def render_image(path):
    """Load an image file and convert to LCD frame."""
    img = Image.open(path)
    img = img.resize((LCD_WIDTH, LCD_HEIGHT))
    img = img.convert("1")  # dither to 1-bit
    return image_to_frame(img)


if __name__ == "__main__":
    from g13.device import G13Device

    print("Testing LCD display...")
    with G13Device() as g13:
        # Show text
        frame = render_text("Hello G13!\nRaspberry Pi 5\nDriver v1.0")
        g13.set_lcd(frame)
        print("Displayed text. Waiting 3s...")
        time.sleep(3)

        # Show clock
        frame = render_clock()
        g13.set_lcd(frame)
        print("Displayed clock. Waiting 3s...")
        time.sleep(3)

        # Show system stats
        frame = render_system_stats()
        g13.set_lcd(frame)
        print("Displayed system stats. Waiting 3s...")
        time.sleep(3)

        print("Done!")
