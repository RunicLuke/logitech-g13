import React, { useState, useEffect } from 'react';
import { HexColorPicker } from 'react-colorful';

const PRESETS = [
  { name: 'Red', hex: '#ff0000' },
  { name: 'Green', hex: '#00ff00' },
  { name: 'Blue', hex: '#0064ff' },
  { name: 'Purple', hex: '#8000ff' },
  { name: 'Cyan', hex: '#00ffff' },
  { name: 'Orange', hex: '#ff8000' },
  { name: 'Yellow', hex: '#ffff00' },
  { name: 'Pink', hex: '#ff40c0' },
  { name: 'White', hex: '#ffffff' },
];

const PROFILES = ['M1', 'M2', 'M3'];

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return { r, g, b };
}

function rgbToHex(r, g, b) {
  return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
}

export default function ColorPicker({ config, onSave }) {
  const [activeProfile, setActiveProfile] = useState(config.active_profile || 'M1');
  const [brightness, setBrightness] = useState(100);

  const profiles = config.profiles || {};
  const profileColor = profiles[activeProfile]?.color || config.backlight;
  const [color, setColor] = useState(rgbToHex(profileColor.r, profileColor.g, profileColor.b));

  useEffect(() => {
    const pc = profiles[activeProfile]?.color || config.backlight;
    setColor(rgbToHex(pc.r, pc.g, pc.b));
  }, [activeProfile]);

  const applyColor = async (hex, bright) => {
    const rgb = hexToRgb(hex);
    await fetch('/api/color', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...rgb, brightness: bright / 100 }),
    });
  };

  const handleColorChange = (hex) => {
    setColor(hex);
    applyColor(hex, brightness);
  };

  const handleBrightness = (e) => {
    const val = parseInt(e.target.value);
    setBrightness(val);
    applyColor(color, val);
  };

  const handlePreset = (hex) => {
    setColor(hex);
    applyColor(hex, brightness);
  };

  const handleSwitchProfile = async (profile) => {
    setActiveProfile(profile);
    await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile }),
    }).catch(() => {});
  };

  const handleSave = () => {
    const rgb = hexToRgb(color);
    const updatedProfiles = { ...profiles };
    updatedProfiles[activeProfile] = {
      ...updatedProfiles[activeProfile],
      color: rgb,
    };
    onSave({ ...config, backlight: rgb, profiles: updatedProfiles });
  };

  return (
    <div className="panel">
      <h2>Backlight Color</h2>

      <h3>Profile</h3>
      <div className="lcd-modes mb-8">
        {PROFILES.map(p => (
          <button
            key={p}
            className={activeProfile === p ? 'active' : ''}
            onClick={() => handleSwitchProfile(p)}
            style={{
              borderBottom: profiles[p]?.color
                ? `3px solid ${rgbToHex(profiles[p].color.r, profiles[p].color.g, profiles[p].color.b)}`
                : undefined,
            }}
          >
            {p}: {profiles[p]?.name || p}
          </button>
        ))}
      </div>

      <div className="color-section">
        <div className="color-picker-wrapper">
          <HexColorPicker color={color} onChange={handleColorChange} />
        </div>
        <div className="color-controls">
          <h3>Presets</h3>
          <div className="color-presets">
            {PRESETS.map(p => (
              <div
                key={p.name}
                className={`color-preset ${color === p.hex ? 'active' : ''}`}
                style={{ backgroundColor: p.hex }}
                title={p.name}
                onClick={() => handlePreset(p.hex)}
              />
            ))}
          </div>

          <div className="slider-group">
            <label>Brightness: {brightness}%</label>
            <input
              type="range"
              min="0"
              max="100"
              value={brightness}
              onChange={handleBrightness}
            />
          </div>

          <div className="slider-group">
            <label>Current: {color}</label>
          </div>

          <button className="btn btn-primary mt-8" onClick={handleSave}>
            Save {activeProfile} Color
          </button>
        </div>
      </div>
    </div>
  );
}
