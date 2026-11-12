import React, { createContext, useContext, useState, useCallback } from 'react';

export interface ToastAlert {
  id: string;
  title: string;
  message: string;
  severity: 'critical' | 'warning' | 'info';
  timestamp: string;
}

interface AlertContextType {
  alerts: ToastAlert[];
  triggerAlert: (alert: Omit<ToastAlert, 'id' | 'timestamp'>) => void;
  removeAlert: (id: string) => void;
}

const AlertContext = createContext<AlertContextType | undefined>(undefined);

// Web Audio API synthesize soft radar chime
const playAlertChime = () => {
  try {
    const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880.0, ctx.currentTime + 0.15); // A5

    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) {
    // Audio context may require prior user interaction
  }
};

export const AlertProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [alerts, setAlerts] = useState<ToastAlert[]>([]);

  const removeAlert = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const triggerAlert = useCallback((alert: Omit<ToastAlert, 'id' | 'timestamp'>) => {
    const newAlert: ToastAlert = {
      ...alert,
      id: Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    };

    playAlertChime();
    setAlerts((prev) => [newAlert, ...prev].slice(0, 4));

    // Auto dismiss after 8s
    setTimeout(() => {
      removeAlert(newAlert.id);
    }, 8000);
  }, [removeAlert]);

  return (
    <AlertContext.Provider value={{ alerts, triggerAlert, removeAlert }}>
      {children}
      {/* Floating Toast Notification Container */}
      <div style={{
        position: 'fixed',
        top: '20px',
        right: '24px',
        zIndex: 10000,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        maxWidth: '420px',
        pointerEvents: 'none'
      }}>
        {alerts.map((alert) => (
          <div
            key={alert.id}
            style={{
              pointerEvents: 'auto',
              background: alert.severity === 'critical' ? 'rgba(30, 10, 15, 0.96)' : 'rgba(15, 23, 42, 0.96)',
              border: `1px solid ${alert.severity === 'critical' ? '#ef4444' : '#3b82f6'}`,
              boxShadow: `0 10px 30px ${alert.severity === 'critical' ? 'rgba(239, 68, 68, 0.35)' : 'rgba(59, 130, 246, 0.35)'}`,
              borderRadius: '12px',
              padding: '14px 18px',
              color: '#fff',
              display: 'flex',
              gap: '12px',
              alignItems: 'flex-start',
              animation: 'slideIn 0.3s ease-out'
            }}
          >
            <div style={{ fontSize: '20px', lineHeight: 1 }}>
              {alert.severity === 'critical' ? '🚨' : '📡'}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ fontSize: '13px', fontWeight: 700, color: alert.severity === 'critical' ? '#f87171' : '#60a5fa' }}>
                  {alert.title}
                </span>
                <span style={{ fontSize: '10px', color: '#94a3b8' }}>{alert.timestamp}</span>
              </div>
              <div style={{ fontSize: '12px', color: '#e2e8f0', lineHeight: 1.4 }}>
                {alert.message}
              </div>
            </div>
            <button
              onClick={() => removeAlert(alert.id)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                fontSize: '14px',
                padding: '2px'
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </AlertContext.Provider>
  );
};

export const useAlert = () => {
  const context = useContext(AlertContext);
  if (!context) throw new Error('useAlert must be used within an AlertProvider');
  return context;
};
