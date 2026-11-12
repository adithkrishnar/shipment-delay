import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

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
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-base)' }}>
      {/* LEFT: Branding */}
      <div style={{ 
        flex: 1, 
        display: 'flex', 
        flexDirection: 'column', 
        justifyContent: 'center', 
        padding: '0 10%', 
        background: 'var(--bg-surface-2)', 
        borderRight: '1px solid var(--border-subtle)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '32px' }}>
          <div className="brand-logo" style={{ width: 48, height: 48, borderRadius: 'var(--r-lg)', background: 'var(--accent-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg style={{ width: 24, height: 24, color: '#fff' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h1 style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>SUPPLYIQ</h1>
        </div>
        <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
          AI-powered supply chain intelligence
        </h2>
        <p style={{ fontSize: '16px', color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: '400px' }}>
          Predict delays, understand inventory risk, and make faster operational decisions.
        </p>
      </div>

      {/* RIGHT: Login Card */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '0 24px' }}>
        <div style={{ width: '100%', maxWidth: '380px', background: 'var(--bg-surface-1)', padding: '40px', borderRadius: 'var(--r-xl)', border: '1px solid var(--border-subtle)', boxShadow: 'var(--shadow-md)' }}>
          <div style={{ marginBottom: '32px', textAlign: 'center' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>Welcome back</h2>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Log in to access your intelligence dashboard</p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <label htmlFor="login-email" style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '8px' }}>Email</label>
              <input
                id="login-email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', color: 'var(--text-primary)', fontSize: '14px' }}
              />
            </div>

            <div>
              <label htmlFor="login-password" style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '8px' }}>Password</label>
              <input
                id="login-password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', color: 'var(--text-primary)', fontSize: '14px' }}
              />
            </div>

            {error && (
              <div style={{ padding: '12px', background: 'var(--status-critical-bg)', color: 'var(--status-critical)', border: '1px solid var(--status-critical-border)', borderRadius: 'var(--r-md)', fontSize: '13px' }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
              style={{ width: '100%', padding: '12px', fontSize: '14px', marginTop: '8px' }}
            >
              {loading ? 'Logging in...' : 'Sign in'}
            </button>
          </form>

          {/* Quick Demo Role Switcher Pills */}
          <div style={{ marginTop: '20px', padding: '12px', background: 'var(--bg-surface-2)', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              One-Click Role Demonstration
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <button
                type="button"
                onClick={() => { setEmail('admin@vanguard-aero.com'); setPassword('vanguard123'); }}
                style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', background: 'var(--bg-base)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span>🚀 <strong>Company: Vanguard Aero</strong></span>
                <span style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>admin@vanguard-aero.com</span>
              </button>
              <button
                type="button"
                onClick={() => { setEmail('ops@pacificintermodal.com'); setPassword('pacific123'); }}
                style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', background: 'var(--bg-base)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span>🚢 <strong>Carrier: Pacific Intermodal</strong></span>
                <span style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>ops@pacificintermodal.com</span>
              </button>
              <button
                type="button"
                onClick={() => { setEmail('admin@dataco.com'); setPassword('admin123'); }}
                style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', background: 'var(--bg-base)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span>🏢 <strong>Company: DataCo Global</strong></span>
                <span style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>admin@dataco.com</span>
              </button>
              <button
                type="button"
                onClick={() => { setEmail('carrier@datacotransport.com'); setPassword('carrier123'); }}
                style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', background: 'var(--bg-base)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span>🚚 <strong>Transporter: DataCo Linehaul</strong></span>
                <span style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>carrier@datacotransport.com</span>
              </button>
            </div>
          </div>

          <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '13px', color: 'var(--text-secondary)' }}>
            Don't have an account? <Link to="/register" style={{ color: 'var(--accent-primary)', fontWeight: 500 }}>Register</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
