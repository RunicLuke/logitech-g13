import React, { useState } from 'react';

const LCD_MODES = ['clock', 'stats', 'message'];

export default function LcdControl({ config, onSave }) {
  const [mode, setMode] = useState(config.lcd_mode || 'clock');
  const [text, setText] = useState(config.lcd_message || '');
  const [scrollText, setScrollText] = useState('Hello from the G13!');
  const [fadeText, setFadeText] = useState('G13');

  const setLcdMode = async (m) => {
    setMode(m);
    await fetch('/api/lcd/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: m }),
    });
  };

  const sendText = async () => {
    await fetch('/api/lcd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
  };

  const startAnimation = async (type, extra = {}) => {
    await fetch('/api/animate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, ...extra }),
    });
  };

  const stopAnimation = async () => {
    await fetch('/api/animate/stop', { method: 'POST' });
  };

  const uploadGif = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('gif', file);
    await fetch('/api/upload/gif', { method: 'POST', body: form });
  };

  const handleSave = () => {
    onSave({ ...config, lcd_mode: mode, lcd_message: text });
  };

  return (
    <div className="panel">
      <h2>LCD Display</h2>

      <h3>Display Mode</h3>
      <div className="lcd-modes">
        {LCD_MODES.map(m => (
          <button
            key={m}
            className={mode === m ? 'active' : ''}
            onClick={() => setLcdMode(m)}
          >
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </button>
        ))}
      </div>

      <h3>Custom Message</h3>
      <textarea
        className="lcd-text-input"
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Type a message to display on the LCD..."
        rows={3}
      />
      <div className="mt-8" style={{ display: 'flex', gap: '8px' }}>
        <button className="btn btn-primary" onClick={sendText}>
          Send to LCD
        </button>
        <button className="btn" onClick={handleSave}>
          Save as Default
        </button>
      </div>

      <h3>Animations</h3>
      <div className="anim-buttons">
        <button onClick={() => startAnimation('matrix')}>
          Matrix Rain
        </button>
        <button onClick={() => startAnimation('progress', { text: 'Loading' })}>
          Progress Bar
        </button>
        <button className="btn-danger" onClick={stopAnimation}>
          Stop Animation
        </button>
      </div>

      <div className="row mt-8">
        <div>
          <label style={{ fontSize: '13px', color: '#aaa', display: 'block', marginBottom: '4px' }}>
            Scrolling Text
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              className="lcd-text-input"
              style={{ minHeight: 'auto', flex: 1 }}
              value={scrollText}
              onChange={e => setScrollText(e.target.value)}
            />
            <button className="btn" onClick={() => startAnimation('scroll', { text: scrollText })}>
              Scroll
            </button>
          </div>
        </div>
      </div>

      <div className="row mt-8">
        <div>
          <label style={{ fontSize: '13px', color: '#aaa', display: 'block', marginBottom: '4px' }}>
            Fade Text
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              className="lcd-text-input"
              style={{ minHeight: 'auto', flex: 1 }}
              value={fadeText}
              onChange={e => setFadeText(e.target.value)}
            />
            <button className="btn" onClick={() => startAnimation('fade', { text: fadeText })}>
              Fade
            </button>
          </div>
        </div>
      </div>

      <div className="gif-upload mt-16">
        <h3>Animated GIF</h3>
        <label htmlFor="gif-file">
          Upload GIF to play on LCD
        </label>
        <input id="gif-file" type="file" accept=".gif" onChange={uploadGif} />
      </div>
    </div>
  );
}
