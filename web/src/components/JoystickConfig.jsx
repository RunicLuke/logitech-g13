import React, { useState } from 'react';

export default function JoystickConfig({ config, onSave }) {
  const [mode, setMode] = useState(config.joystick_mode || 'mouse');
  const [sensitivity, setSensitivity] = useState(config.joystick_sensitivity || 5);
  const [deadzone, setDeadzone] = useState(config.joystick_deadzone || 20);

  const handleSave = () => {
    onSave({
      ...config,
      joystick_mode: mode,
      joystick_sensitivity: sensitivity,
      joystick_deadzone: deadzone,
    });
  };

  return (
    <div className="panel">
      <h2>Joystick Settings</h2>

      <h3>Mode</h3>
      <div className="joystick-options">
        <label>
          <input
            type="radio"
            name="joy-mode"
            value="mouse"
            checked={mode === 'mouse'}
            onChange={() => setMode('mouse')}
          />
          Mouse (move cursor)
        </label>
        <label>
          <input
            type="radio"
            name="joy-mode"
            value="arrows"
            checked={mode === 'arrows'}
            onChange={() => setMode('arrows')}
          />
          Arrow Keys
        </label>
        <label>
          <input
            type="radio"
            name="joy-mode"
            value="scroll"
            checked={mode === 'scroll'}
            onChange={() => setMode('scroll')}
          />
          Scroll Wheel
        </label>
      </div>

      <div className="slider-group">
        <label>Sensitivity: {sensitivity}</label>
        <input
          type="range"
          min="1"
          max="20"
          value={sensitivity}
          onChange={e => setSensitivity(parseInt(e.target.value))}
        />
      </div>

      <div className="slider-group">
        <label>Deadzone: {deadzone}</label>
        <input
          type="range"
          min="5"
          max="60"
          value={deadzone}
          onChange={e => setDeadzone(parseInt(e.target.value))}
        />
      </div>

      <button className="btn btn-primary mt-16" onClick={handleSave}>
        Save Settings
      </button>
    </div>
  );
}
