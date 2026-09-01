import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const result = await login(email, password);
    if (result.success) {
      navigate('/');
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="boot">
      <div className="brand-mark">S</div>
      <h2>Welcome to SupplyIQ</h2>
      <p>Log in to access your intelligence dashboard</p>
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '300px', margin: '2rem auto' }}>
        <input
          type="email"
          placeholder="Email address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{ padding: '0.8rem', borderRadius: '4px', border: '1px solid #ccc' }}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{ padding: '0.8rem', borderRadius: '4px', border: '1px solid #ccc' }}
        />
        <button type="submit" className="primary" style={{ padding: '0.8rem' }}>Log In</button>
      </form>
      {error && <p className="error" style={{ color: 'red' }}>{error}</p>}
      
      <p style={{ color: '#7f90a7', fontSize: '14px', marginTop: '20px' }}>
        Don't have an account? <Link to="/register" style={{ color: '#38bdf8', textDecoration: 'none' }}>Register here</Link>
      </p>
    </div>
  );
}
