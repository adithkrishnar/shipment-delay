import React from 'react';
import { useAuth } from '../auth/AuthContext';

export default function Topbar({company, companies, onCompany}) {
  const { user, logout } = useAuth();
  
  return (
    <header className="topbar">
      <div>
        <span className="eyebrow">SUPPLY CHAIN COMMAND CENTER</span>
        <h1>{company?.name || 'SupplyIQ'}</h1>
      </div>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {companies && companies.length > 0 && (
          <select value={company?.id || ''} onChange={e => onCompany(Number(e.target.value))}>
            {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
        
        {user && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '0.9rem', color: '#666' }}>{user.email}</span>
            <button className="secondary" onClick={logout}>Logout</button>
          </div>
        )}
      </div>
    </header>
  );
}
