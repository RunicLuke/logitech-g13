import React, { useState, useEffect } from 'react';

const KEY_LAYOUT = [
  ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7'],
  ['G8', 'G9', 'G10', 'G11', 'G12', 'G13', 'G14'],
  ['G15', 'G16', 'G17', 'G18', 'G19'],
  ['G20', 'G21', 'G22'],
];

const EXTRA_KEYS = ['LEFT', 'DOWN', 'TOP'];
const MEMORY_KEYS = ['L1', 'L2', 'L3', 'L4'];
const PROFILES = ['M1', 'M2', 'M3'];

const BINDING_TYPES = [
  { value: 'key', label: 'Single Key' },
  { value: 'type', label: 'Type Text' },
  { value: 'combo', label: 'Key Combo' },
  { value: 'cmd', label: 'Shell Command' },
  { value: 'macro', label: 'Macro' },
];

function parseBindingType(binding) {
  if (!binding) return { type: 'key', value: '' };
  if (binding.startsWith('TYPE:')) return { type: 'type', value: binding.slice(5) };
  if (binding.startsWith('COMBO:')) return { type: 'combo', value: binding.slice(6) };
  if (binding.startsWith('CMD:')) return { type: 'cmd', value: binding.slice(4) };
  if (binding.startsWith('MACRO:')) return { type: 'macro', value: binding.slice(6) };
  return { type: 'key', value: binding };
}

function buildBinding(type, value) {
  if (!value) return '';
  switch (type) {
    case 'type': return `TYPE:${value}`;
    case 'combo': return `COMBO:${value}`;
    case 'cmd': return `CMD:${value}`;
    case 'macro': return `MACRO:${value}`;
    default: return value;
  }
}

export default function KeyBindings({ config, onSave }) {
  const [activeProfile, setActiveProfile] = useState(config.active_profile || 'M1');
  const [selectedKey, setSelectedKey] = useState(null);
  const [keycodes, setKeycodes] = useState([]);
  const [bindingType, setBindingType] = useState('key');
  const [bindingValue, setBindingValue] = useState('');

  const profiles = config.profiles || {
    M1: { name: 'Default', bindings: config.bindings || {} },
    M2: { name: 'Profile 2', bindings: {} },
    M3: { name: 'Profile 3', bindings: {} },
  };

  const currentBindings = profiles[activeProfile]?.bindings || {};
  const profileName = profiles[activeProfile]?.name || activeProfile;

  useEffect(() => {
    fetch('/api/keycodes').then(r => r.json()).then(setKeycodes);
  }, []);

  useEffect(() => {
    if (selectedKey && currentBindings[selectedKey]) {
      const parsed = parseBindingType(currentBindings[selectedKey]);
      setBindingType(parsed.type);
      setBindingValue(parsed.value);
    } else {
      setBindingType('key');
      setBindingValue('');
    }
  }, [selectedKey, activeProfile]);

  const handleSwitchProfile = async (profile) => {
    setActiveProfile(profile);
    setSelectedKey(null);
    await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile }),
    }).catch(() => {});
  };

  const handleUpdateBinding = (newBinding) => {
    const updatedProfiles = { ...profiles };
    updatedProfiles[activeProfile] = {
      ...updatedProfiles[activeProfile],
      bindings: { ...currentBindings, [selectedKey]: newBinding },
    };
    onSave({ ...config, profiles: updatedProfiles });
  };

  const handleBindingChange = () => {
    const binding = buildBinding(bindingType, bindingValue);
    if (binding) handleUpdateBinding(binding);
  };

  const handleClear = () => {
    const updatedProfiles = { ...profiles };
    const newBindings = { ...currentBindings };
    delete newBindings[selectedKey];
    updatedProfiles[activeProfile] = {
      ...updatedProfiles[activeProfile],
      bindings: newBindings,
    };
    onSave({ ...config, profiles: updatedProfiles });
    setBindingValue('');
  };

  const handleRenameProfile = (name) => {
    const updatedProfiles = { ...profiles };
    updatedProfiles[activeProfile] = {
      ...updatedProfiles[activeProfile],
      name,
    };
    onSave({ ...config, profiles: updatedProfiles });
  };

  const getDisplayBinding = (binding) => {
    if (!binding) return '---';
    if (binding.length > 12) return binding.slice(0, 11) + '...';
    return binding;
  };

  return (
    <div className="panel">
      <h2>Key Bindings</h2>

      <h3>Profile</h3>
      <div className="lcd-modes mb-8">
        {PROFILES.map(p => (
          <button
            key={p}
            className={activeProfile === p ? 'active' : ''}
            onClick={() => handleSwitchProfile(p)}
          >
            {p}: {profiles[p]?.name || p}
          </button>
        ))}
      </div>

      <div style={{ marginBottom: '16px' }}>
        <label style={{ fontSize: '13px', color: '#aaa', marginRight: '8px' }}>Profile Name:</label>
        <input
          type="text"
          className="lcd-text-input"
          style={{ minHeight: 'auto', width: '200px', display: 'inline-block' }}
          value={profileName}
          onChange={e => handleRenameProfile(e.target.value)}
        />
      </div>

      <p style={{ fontSize: '13px', color: '#888', marginBottom: '12px' }}>
        Click a key to edit its binding.
      </p>

      <div className="key-grid">
        <h3>Memory Keys</h3>
        <div className="key-row">
          {MEMORY_KEYS.map(key => (
            <div
              key={key}
              className={`key-btn ${selectedKey === key ? 'selected' : ''}`}
              onClick={() => setSelectedKey(key)}
            >
              <div className="key-name">{key}</div>
              <div className="key-binding">{getDisplayBinding(currentBindings[key])}</div>
            </div>
          ))}
        </div>
        {KEY_LAYOUT.map((row, ri) => (
          <div key={ri} className="key-row">
            {row.map(key => (
              <div
                key={key}
                className={`key-btn ${selectedKey === key ? 'selected' : ''}`}
                onClick={() => setSelectedKey(key)}
              >
                <div className="key-name">{key}</div>
                <div className="key-binding">{getDisplayBinding(currentBindings[key])}</div>
              </div>
            ))}
          </div>
        ))}
        <h3>Joystick</h3>
        <div className="key-row">
          {EXTRA_KEYS.map(key => (
            <div
              key={key}
              className={`key-btn ${selectedKey === key ? 'selected' : ''}`}
              onClick={() => setSelectedKey(key)}
            >
              <div className="key-name">{key}</div>
              <div className="key-binding">{getDisplayBinding(currentBindings[key])}</div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
          BD button is reserved for the on-device menu (press to open/close).
        </p>
      </div>

      {selectedKey && (
        <div className="binding-editor">
          <label>Binding for {selectedKey}:</label>

          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', marginTop: '8px' }}>
            {BINDING_TYPES.map(bt => (
              <button
                key={bt.value}
                className={`btn ${bindingType === bt.value ? 'btn-primary' : ''}`}
                onClick={() => { setBindingType(bt.value); setBindingValue(''); }}
                style={{ fontSize: '12px', padding: '6px 10px' }}
              >
                {bt.label}
              </button>
            ))}
          </div>

          {bindingType === 'key' && (
            <select
              value={bindingValue}
              onChange={e => { setBindingValue(e.target.value); handleUpdateBinding(e.target.value); }}
            >
              <option value="">-- Select Key --</option>
              {keycodes.map(k => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          )}

          {bindingType === 'type' && (
            <div>
              <textarea
                className="lcd-text-input"
                value={bindingValue}
                onChange={e => setBindingValue(e.target.value)}
                placeholder="Text to type (use \n for Enter, \t for Tab)"
                rows={2}
              />
              <button className="btn btn-primary mt-8" onClick={handleBindingChange}>
                Set Binding
              </button>
            </div>
          )}

          {bindingType === 'combo' && (
            <div>
              <input
                type="text"
                className="lcd-text-input"
                style={{ minHeight: 'auto' }}
                value={bindingValue}
                onChange={e => setBindingValue(e.target.value)}
                placeholder="e.g. LEFTCTRL+C or LEFTCTRL+LEFTSHIFT+P"
              />
              <p style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                Separate keys with + (e.g. LEFTCTRL+S, LEFTALT+F4)
              </p>
              <button className="btn btn-primary mt-8" onClick={handleBindingChange}>
                Set Binding
              </button>
            </div>
          )}

          {bindingType === 'cmd' && (
            <div>
              <input
                type="text"
                className="lcd-text-input"
                style={{ minHeight: 'auto' }}
                value={bindingValue}
                onChange={e => setBindingValue(e.target.value)}
                placeholder="Shell command to run (e.g. notify-send hello)"
              />
              <button className="btn btn-primary mt-8" onClick={handleBindingChange}>
                Set Binding
              </button>
            </div>
          )}

          {bindingType === 'macro' && (
            <div>
              <textarea
                className="lcd-text-input"
                value={bindingValue}
                onChange={e => setBindingValue(e.target.value)}
                placeholder="Comma-separated steps: COMBO:LEFTCTRL+S,DELAY:200,TYPE:npm run build\n"
                rows={3}
              />
              <p style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                Steps: COMBO:keys, TYPE:text, CMD:command, DELAY:ms
              </p>
              <button className="btn btn-primary mt-8" onClick={handleBindingChange}>
                Set Binding
              </button>
            </div>
          )}

          <div className="mt-8">
            <button className="btn btn-danger" onClick={handleClear}>
              Clear Binding
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
