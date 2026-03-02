import React, { useState, useEffect } from 'react';
import ColorPicker from './components/ColorPicker.jsx';
import LcdControl from './components/LcdControl.jsx';
import KeyBindings from './components/KeyBindings.jsx';
import JoystickConfig from './components/JoystickConfig.jsx';
import AlarmConfig from './components/AlarmConfig.jsx';

const API = '/api';

export default function App() {
  const [tab, setTab] = useState('backlight');
  const [config, setConfig] = useState(null);
  const [daemonRunning, setDaemonRunning] = useState(false);

  useEffect(() => {
    fetch(`${API}/status`).then(r => r.json()).then(d => setDaemonRunning(d.daemon));
    fetch(`${API}/config`).then(r => r.json()).then(setConfig);
  }, []);

  const saveConfig = async (newConfig) => {
    setConfig(newConfig);
    await fetch(`${API}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig),
    });
  };

  if (!config) return <div className="app"><p>Loading...</p></div>;

  const tabs = [
    { id: 'backlight', label: 'Backlight' },
    { id: 'lcd', label: 'LCD' },
    { id: 'keys', label: 'Keys' },
    { id: 'joystick', label: 'Joystick' },
    { id: 'alarms', label: 'Alarms' },
  ];

  return (
    <div className="app">
      <div className="header">
        <h1>G13 Control Panel</h1>
        <div className={`status ${daemonRunning ? 'connected' : ''}`}>
          Daemon: {daemonRunning ? 'Running' : 'Not Running'}
        </div>
      </div>

      <div className="tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            className={tab === t.id ? 'active' : ''}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'backlight' && (
        <ColorPicker config={config} onSave={saveConfig} />
      )}
      {tab === 'lcd' && (
        <LcdControl config={config} onSave={saveConfig} />
      )}
      {tab === 'keys' && (
        <KeyBindings config={config} onSave={saveConfig} />
      )}
      {tab === 'joystick' && (
        <JoystickConfig config={config} onSave={saveConfig} />
      )}
      {tab === 'alarms' && (
        <AlarmConfig config={config} onSave={saveConfig} />
      )}
    </div>
  );
}
