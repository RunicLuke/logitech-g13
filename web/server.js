import express from 'express';
import cors from 'cors';
import multer from 'multer';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = 3113;
const DAEMON_TCP_PORT = 3114;
const DAEMON_SOCKET = '/tmp/g13daemon.sock';
const CONFIG_PATH = path.join(__dirname, '..', 'config.json');
const UPLOAD_DIR = path.join(__dirname, 'uploads');

app.use(cors());
app.use(express.json());

// Serve built React app
app.use(express.static(path.join(__dirname, 'dist')));

// File upload for GIFs
const upload = multer({ dest: UPLOAD_DIR });

// Send command to the Python daemon via TCP
function sendToDaemon(cmd) {
  return new Promise((resolve, reject) => {
    const client = new net.Socket();
    client.setTimeout(2000);

    client.connect(DAEMON_TCP_PORT, '127.0.0.1', () => {
      client.write(JSON.stringify(cmd));
      client.end();
      resolve();
    });

    client.on('error', (err) => {
      reject(err);
    });

    client.on('timeout', () => {
      client.destroy();
      reject(new Error('Connection timed out'));
    });
  });
}

// Check if daemon is running
function isDaemonRunning() {
  return fs.existsSync(DAEMON_SOCKET);
}

// API: Get status
app.get('/api/status', (req, res) => {
  res.json({ daemon: isDaemonRunning() });
});

// API: Get config
app.get('/api/config', (req, res) => {
  try {
    const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
    res.json(config);
  } catch (err) {
    res.status(500).json({ error: 'Failed to read config' });
  }
});

// API: Save config
app.post('/api/config', async (req, res) => {
  try {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(req.body, null, 4));
    if (isDaemonRunning()) {
      await sendToDaemon({ action: 'reload' });
    }
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: Set color
app.post('/api/color', async (req, res) => {
  try {
    const { r, g, b, brightness = 1.0 } = req.body;
    await sendToDaemon({ action: 'color', r, g, b, brightness });
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: Set LCD text
app.post('/api/lcd', async (req, res) => {
  try {
    const { text } = req.body;
    await sendToDaemon({ action: 'lcd', text });
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: Set LCD mode
app.post('/api/lcd/mode', async (req, res) => {
  try {
    const { mode } = req.body;
    await sendToDaemon({ action: 'lcd_mode', mode });
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: Start animation
app.post('/api/animate', async (req, res) => {
  try {
    await sendToDaemon({ action: 'animate', ...req.body });
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: Stop animation
app.post('/api/animate/stop', async (req, res) => {
  try {
    await sendToDaemon({ action: 'animate_stop' });
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: Upload GIF and start animation
app.post('/api/upload/gif', upload.single('gif'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }
    const gifPath = req.file.path;
    await sendToDaemon({ action: 'animate', type: 'gif', path: gifPath });
    res.json({ ok: true, path: gifPath });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: Switch profile
app.post('/api/profile', async (req, res) => {
  try {
    const { profile } = req.body;
    await sendToDaemon({ action: 'profile', profile });
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: Get available key codes
app.get('/api/keycodes', (req, res) => {
  const keycodes = [
    'ESC', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
    'MINUS', 'EQUAL', 'BACKSPACE', 'TAB',
    'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P',
    'LEFTBRACE', 'RIGHTBRACE', 'ENTER', 'LEFTCTRL',
    'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L',
    'SEMICOLON', 'APOSTROPHE', 'GRAVE', 'LEFTSHIFT', 'BACKSLASH',
    'Z', 'X', 'C', 'V', 'B', 'N', 'M',
    'COMMA', 'DOT', 'SLASH', 'RIGHTSHIFT', 'LEFTALT', 'SPACE', 'CAPSLOCK',
    'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
    'UP', 'DOWN', 'LEFT', 'RIGHT',
    'PAGEUP', 'PAGEDOWN', 'HOME', 'END', 'INSERT', 'DELETE', 'PAUSE',
    'LEFTMETA', 'RIGHTMETA', 'RIGHTCTRL', 'RIGHTALT',
    'VOLUMEUP', 'VOLUMEDOWN', 'MUTE', 'PLAYPAUSE', 'NEXTSONG', 'PREVIOUSSONG',
    'MOUSE_LEFT', 'MOUSE_RIGHT', 'MOUSE_MIDDLE',
  ];
  res.json(keycodes);
});

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`G13 Web GUI running at http://0.0.0.0:${PORT}`);
  console.log(`Daemon socket: ${DAEMON_SOCKET} (${isDaemonRunning() ? 'running' : 'not running'})`);
});
