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
      navigate('/');
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="boot" style={{ justifyContent: 'center' }}>
      {/* Brand mark */}
      <div style={{ marginBottom: 0, textAlign: 'center' }}>
        <div className="brand-logo" style={{ width: 40, height: 40, borderRadius: 10, margin: '0 auto 12px' }}>
          <svg style={{ position: 'relative', zIndex: 1, width: 20, height: 20 }} viewBox="0 0 14 14" fill="none">
            <path d="M7 1L12 4v6l-5 3L2 10V4l5-3z" stroke="#040810" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
            <path d="M7 5l3 1.75v3.5L7 12l-3-1.75V6.75L7 5z" fill="#040810" opacity="0.6"/>
          </svg>
        </div>
      </div>

      <div className="auth-card animate-up">
        <div className="auth-header">
          <h2>Welcome back</h2>
          <p>Log in to access your intelligence dashboard</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label className="form-label" htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              className="form-input"
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              className="form-input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="error" style={{ marginTop: 0 }}>{error}</div>
          )}

          <button
            type="submit"
            className="primary full"
            disabled={loading}
            style={{ marginTop: 4 }}
          >
            {loading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}>
                <span className="spinner" style={{ width: 13, height: 13, borderWidth: 2 }} aria-hidden="true" />
                Logging in…
              </span>
            ) : 'Log in'}
          </button>
        </form>

        <div className="auth-link">
          Don't have an account?{' '}
          <Link to="/register">Register here</Link>
        </div>
      </div>
    </div>
  );
}
