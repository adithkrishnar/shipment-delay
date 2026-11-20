import React from 'react';
import { useAuth } from '../auth/AuthContext';
import { LogOut } from 'lucide-react';

export default function Topbar({ company, companies, onCompany }) {
  const { user, logout } = useAuth();

  return (
    <header className="topbar" role="banner">
      <div className="topbar-left">
        {company && (
          <div className="topbar-company-name">
            {company.name}
          </div>
        )}
      </div>

      <div className="topbar-right">
        {user?.participant_role && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              background: user.participant_role === 'sender' ? 'rgba(56, 189, 248, 0.12)' :
                          user.participant_role === 'receiver' ? 'rgba(52, 211, 153, 0.12)' :
                          user.participant_role === 'transporter' ? 'rgba(251, 146, 60, 0.12)' : 'var(--bg-surface-2)',
              border: `1px solid ${
                user.participant_role === 'sender' ? 'rgba(56, 189, 248, 0.3)' :
                user.participant_role === 'receiver' ? 'rgba(52, 211, 153, 0.3)' :
                user.participant_role === 'transporter' ? 'rgba(251, 146, 60, 0.3)' : 'var(--border-default)'
              }`,
              borderRadius: 'var(--r-md)',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: user.participant_role === 'sender' ? '#38BDF8' :
                     user.participant_role === 'receiver' ? '#34D399' :
                     user.participant_role === 'transporter' ? '#FB923C' : 'var(--text-secondary)'
            }}
          >
            <span>ROLE:</span>
            <span>
              {user.participant_role === 'sender' ? 'Sender (Consignor)' :
               user.participant_role === 'receiver' ? 'Receiver (Consignee)' :
               user.participant_role === 'transporter' ? 'Transporter (Carrier)' : user.participant_role}
            </span>
          </div>
        )}

        {company && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              background: 'var(--bg-surface-2)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--r-md)',
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--text-primary)'
            }}
          >
            <span style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>
              Tenant Scope:
            </span>
            {user?.is_superuser && companies && companies.length > 1 ? (
              <select
                aria-label="Select Tenant Scope"
                value={company.id}
                onChange={e => onCompany && onCompany(Number(e.target.value))}
                style={{
                  background: 'transparent',
                  color: 'var(--accent-primary)',
                  border: 'none',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  outline: 'none',
                  paddingRight: '4px'
                }}
              >
                {companies.map(c => (
                  <option key={c.id} value={c.id} style={{ background: '#1A232E', color: '#F3F6FA' }}>
                    {c.name}
                  </option>
                ))}
              </select>
            ) : (
              <span style={{ color: 'var(--accent-primary)', fontWeight: 700 }}>
                {company.name}
              </span>
            )}
          </div>
        )}

        {user && (
          <div className="flex-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-healthy)', boxShadow: '0 0 0 2px var(--status-healthy-bg)' }} />
              <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }} title={user.email}>{user.email}</span>
            </div>
            <button
              className="btn-secondary"
              onClick={logout}
              aria-label="Log out"
            >
              <LogOut size={14} aria-hidden="true" />
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
