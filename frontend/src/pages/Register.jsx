import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function Register() {
  const [companyName, setCompanyName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsRegistering(true);
    
    const result = await register(email, password, companyName);
    
    setIsRegistering(false);
    
    if (result.success) {
      navigate('/');
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="boot">
      <div className="brand-mark">S</div>
      <h2>Join SupplyIQ</h2>
      <p>Create an account and set up your company space</p>
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '300px', margin: '2rem auto' }}>
        <input
          type="text"
          placeholder="Company Name"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          required
          style={{ padding: '0.8rem', borderRadius: '4px', border: '1px solid #203049', background: '#0b1220', color: '#e6edf7' }}
        />
        <input
          type="email"
          placeholder="Email address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{ padding: '0.8rem', borderRadius: '4px', border: '1px solid #203049', background: '#0b1220', color: '#e6edf7' }}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{ padding: '0.8rem', borderRadius: '4px', border: '1px solid #203049', background: '#0b1220', color: '#e6edf7' }}
        />
        <button type="submit" className="primary" style={{ padding: '0.8rem' }} disabled={isRegistering}>
          {isRegistering ? 'Registering...' : 'Register'}
        </button>
      </form>
      
      {error && <p className="error" style={{ color: '#f87171', border: 'none', padding: 0, margin: '-10px 0 10px' }}>{error}</p>}
      
      <p style={{ color: '#7f90a7', fontSize: '14px' }}>
        Already have an account? <Link to="/login" style={{ color: '#38bdf8', textDecoration: 'none' }}>Log in here</Link>
      </p>
    </div>
  );
}
