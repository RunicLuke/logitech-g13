import React, { useState } from 'react';

const DEFAULT_ALARM = {
  time: '00:00',
  enabled: false,
  actions: ['display'],
  message: '',
  command: '',
};

const ACTION_OPTIONS = [
  { id: 'display', label: 'Show Message', desc: 'Display message on LCD for 10 seconds' },
  { id: 'flash', label: 'Flash Backlight', desc: 'Flash backlight red for 10 seconds' },
  { id: 'command', label: 'Run Command', desc: 'Execute a shell command' },
];

export default function AlarmConfig({ config, onSave }) {
  const alarms = (config.alarms || []).map(a => ({ ...DEFAULT_ALARM, ...a }));
  while (alarms.length < 3) alarms.push({ ...DEFAULT_ALARM });

  const [expanded, setExpanded] = useState(null);

  const updateAlarm = (idx, changes) => {
    const updated = alarms.map((a, i) => i === idx ? { ...a, ...changes } : a);
    onSave({ ...config, alarms: updated });
  };

  const toggleAction = (idx, actionId) => {
    const alarm = alarms[idx];
    const actions = alarm.actions.includes(actionId)
      ? alarm.actions.filter(a => a !== actionId)
      : [...alarm.actions, actionId];
    updateAlarm(idx, { actions });
  };

  return (
    <div className="panel">
      <h2>Alarms</h2>
      <p style={{ fontSize: '13px', color: '#888', marginBottom: '16px' }}>
        Set up to 3 alarms. When triggered, alarms can show a message on the LCD,
        flash the backlight, or run a shell command.
      </p>

      {alarms.slice(0, 3).map((alarm, idx) => (
        <div
          key={idx}
          className="alarm-card"
          style={{
            border: '1px solid #333',
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '12px',
            background: alarm.enabled ? '#1a2a1a' : '#1a1a1a',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: expanded === idx ? '12px' : 0 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={alarm.enabled}
                onChange={e => updateAlarm(idx, { enabled: e.target.checked })}
              />
              <span style={{ fontWeight: 'bold', color: alarm.enabled ? '#4f4' : '#888' }}>
                Alarm {idx + 1}
              </span>
            </label>

            <input
              type="time"
              value={alarm.time || '00:00'}
              onChange={e => updateAlarm(idx, { time: e.target.value })}
              style={{
                background: '#222',
                border: '1px solid #444',
                color: '#fff',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '16px',
              }}
            />

            <span style={{ fontSize: '12px', color: '#666', flex: 1 }}>
              {alarm.actions.length > 0 ? alarm.actions.join(', ') : 'no actions'}
            </span>

            <button
              className="btn"
              style={{ padding: '4px 12px', fontSize: '12px' }}
              onClick={() => setExpanded(expanded === idx ? null : idx)}
            >
              {expanded === idx ? 'Collapse' : 'Edit'}
            </button>
          </div>

          {expanded === idx && (
            <div style={{ borderTop: '1px solid #333', paddingTop: '12px' }}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ fontSize: '13px', color: '#aaa', display: 'block', marginBottom: '4px' }}>
                  Actions
                </label>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {ACTION_OPTIONS.map(opt => (
                    <button
                      key={opt.id}
                      className={`btn ${alarm.actions.includes(opt.id) ? 'btn-primary' : ''}`}
                      style={{ fontSize: '12px', padding: '6px 12px' }}
                      onClick={() => toggleAction(idx, opt.id)}
                      title={opt.desc}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {alarm.actions.includes('display') && (
                <div style={{ marginBottom: '12px' }}>
                  <label style={{ fontSize: '13px', color: '#aaa', display: 'block', marginBottom: '4px' }}>
                    Display Message
                  </label>
                  <input
                    type="text"
                    className="lcd-text-input"
                    style={{ minHeight: 'auto' }}
                    value={alarm.message}
                    onChange={e => updateAlarm(idx, { message: e.target.value })}
                    placeholder={`Alarm ${idx + 1}!`}
                  />
                </div>
              )}

              {alarm.actions.includes('command') && (
                <div style={{ marginBottom: '12px' }}>
                  <label style={{ fontSize: '13px', color: '#aaa', display: 'block', marginBottom: '4px' }}>
                    Shell Command
                  </label>
                  <input
                    type="text"
                    className="lcd-text-input"
                    style={{ minHeight: 'auto' }}
                    value={alarm.command}
                    onChange={e => updateAlarm(idx, { command: e.target.value })}
                    placeholder="e.g. aplay /path/to/alarm.wav"
                  />
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
