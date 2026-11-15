import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Building2, Plane, Ship, Truck } from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.success) {
      if (result.user?.role === 'transporter') {
        navigate('/transporter');
      } else {
        navigate('/');
      }
    } else {
      setError(result.error);
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#070708', position: 'relative' }}>
      {/* LEFT: Cinematic Precision Brand Panel */}
      <div style={{ 
        flex: 1.1, 
        display: 'flex', 
        flexDirection: 'column', 
        justifyContent: 'space-between', 
        padding: '64px 8%', 
        background: '#0D0E10', 
        borderRight: '1px solid #1E2024',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Subtle grid pattern background */}
        <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(to right, rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.015) 1px, transparent 1px)', backgroundSize: '40px 40px', pointerEvents: 'none' }} />

        <div style={{ position: 'relative', zIndex: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <div style={{ width: 32, height: 32, borderRadius: 6, background: '#5E6BFF', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(94, 107, 255, 0.45)' }}>
              <svg width="16" height="16" viewBox="0 0 14 14" fill="none">
                <path d="M7 1L12 4v6l-5 3L2 10V4l5-3z" stroke="#FFFFFF" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
              </svg>
            </div>
            <span style={{ fontFamily: 'Manrope', fontSize: '18px', fontWeight: 700, color: '#F0F1F2', letterSpacing: '0.05em' }}>SUPPLYIQ</span>
          </div>
          <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono', color: '#50D8E9', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            SYSTEM.CORRIDOR // v2.4_PROD
          </span>
        </div>

        <div style={{ position: 'relative', zIndex: 10, maxWidth: '480px', margin: '48px 0' }}>
          <h1 style={{ fontFamily: 'Manrope', fontSize: '38px', fontWeight: 600, color: '#F0F1F2', lineHeight: 1.15, letterSpacing: '-0.04em', marginBottom: '16px' }}>
            The command dashboard for high-velocity supply networks.
          </h1>
          <p style={{ fontSize: '14px', color: '#9A9DA3', lineHeight: 1.6, marginBottom: '24px' }}>
            Predict transit disruptions, quantify inventory consequence, and simulate contingency replenishment in real-time.
          </p>

          {/* Telemetry pill */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '10px', padding: '6px 12px', background: '#141518', border: '1px solid #232426', borderRadius: 4 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#38E5A3', boxShadow: '0 0 8px #38E5A3' }} />
            <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono', color: '#9A9DA3' }}>TELEMETRY SYNCHRONIZED • LATENCY 1.2ms</span>
          </div>
        </div>

        <div style={{ position: 'relative', zIndex: 10, display: 'flex', gap: '24px', fontSize: '12px', color: '#63666E' }}>
          <span>© 2026 SupplyIQ Platform</span>
          <span>•</span>
          <span>Enterprise Decision Support</span>
          <span>•</span>
          <span>Multi-Tenant Architecture</span>
        </div>
      </div>

      {/* RIGHT: Login Form */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '32px 24px', background: '#070708' }}>
        <div style={{ width: '100%', maxWidth: '400px', background: '#101112', padding: '36px', borderRadius: '8px', border: '1px solid #232426', boxShadow: '0 8px 32px rgba(0,0,0,0.6)' }}>
          <div style={{ marginBottom: '28px' }}>
            <h2 style={{ fontFamily: 'Manrope', fontSize: '20px', fontWeight: 600, color: '#F0F1F2', marginBottom: '6px', letterSpacing: '-0.03em' }}>Log in to Workspace</h2>
            <p style={{ fontSize: '13px', color: '#9A9DA3' }}>Access telemetry, delay simulator, and action center</p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <label htmlFor="login-email" style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#9A9DA3', marginBottom: '6px' }}>Email address</label>
              <input
                id="login-email"
                type="email"
                placeholder="operator@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{ width: '100%', padding: '9px 12px', background: '#0A0A0B', border: '1px solid #1E2024', borderRadius: '4px', color: '#F0F1F2', fontSize: '13px' }}
              />
            </div>

            <div>
              <label htmlFor="login-password" style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#9A9DA3', marginBottom: '6px' }}>Password</label>
              <input
                id="login-password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{ width: '100%', padding: '9px 12px', background: '#0A0A0B', border: '1px solid #1E2024', borderRadius: '4px', color: '#F0F1F2', fontSize: '13px' }}
              />
            </div>

            {error && (
              <div style={{ padding: '10px 12px', background: 'rgba(255,90,107,0.08)', color: '#FF5A6B', border: '1px solid rgba(255,90,107,0.2)', borderRadius: '4px', fontSize: '12.5px' }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
              style={{ width: '100%', padding: '10px', fontSize: '13px', marginTop: '6px' }}
            >
              {loading ? 'Authenticating...' : 'Sign in to Console'}
            </button>
          </form>

          {/* Quick Demo Role Switcher Pills */}
          <div style={{ marginTop: '24px', padding: '14px', background: '#0C0D0E', borderRadius: '6px', border: '1px solid #1B1C1E' }}>
            <div style={{ fontSize: '10.5px', fontFamily: 'Manrope', fontWeight: 600, color: '#63666E', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              One-Click Role Demonstration
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <button
                type="button"
                onClick={() => { setEmail('admin@dataco.com'); setPassword('admin123'); }}
                style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', background: '#121315', border: '1px solid #232426', borderRadius: '4px', color: '#F0F1F2', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'border-color 0.15s ease' }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Building2 size={13} color="#5E6BFF" /> <strong>DataCo Global</strong></span>
                <span style={{ color: '#9A9DA3', fontSize: '11px', fontFamily: 'JetBrains Mono' }}>admin@dataco.com</span>
              </button>
              <button
                type="button"
                onClick={() => { setEmail('admin@vanguard-aero.com'); setPassword('vanguard123'); }}
                style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', background: '#121315', border: '1px solid #232426', borderRadius: '4px', color: '#F0F1F2', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'border-color 0.15s ease' }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Plane size={13} color="#50D8E9" /> <strong>Vanguard Aero</strong></span>
                <span style={{ color: '#9A9DA3', fontSize: '11px', fontFamily: 'JetBrains Mono' }}>admin@vanguard-aero.com</span>
              </button>
              <button
                type="button"
                onClick={() => { setEmail('ops@pacificintermodal.com'); setPassword('pacific123'); }}
                style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', background: '#121315', border: '1px solid #232426', borderRadius: '4px', color: '#F0F1F2', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'border-color 0.15s ease' }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Ship size={13} color="#38D39F" /> <strong>Pacific Intermodal</strong></span>
                <span style={{ color: '#9A9DA3', fontSize: '11px', fontFamily: 'JetBrains Mono' }}>ops@pacificintermodal.com</span>
              </button>
              <button
                type="button"
                onClick={() => { setEmail('carrier@datacotransport.com'); setPassword('carrier123'); }}
                style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', background: '#121315', border: '1px solid #232426', borderRadius: '4px', color: '#F0F1F2', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'border-color 0.15s ease' }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Truck size={13} color="#FF9F43" /> <strong>DataCo Linehaul</strong></span>
                <span style={{ color: '#9A9DA3', fontSize: '11px', fontFamily: 'JetBrains Mono' }}>carrier@datacotransport.com</span>
              </button>
            </div>
          </div>

          <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '12px', color: '#9A9DA3' }}>
            New organization? <Link to="/register" style={{ color: '#5E6BFF', fontWeight: 500 }}>Create an account</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
