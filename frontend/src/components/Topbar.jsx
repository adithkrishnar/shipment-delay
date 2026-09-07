import React from 'react';
import { useAuth } from '../auth/AuthContext';
import { LogOut, ChevronDown } from 'lucide-react';

export default function Topbar({ company, companies, onCompany }) {
  const { user, logout } = useAuth();

  return (
    <header className="topbar" role="banner">
      <div className="topbar-left">
        {company && (
          <>
            <span className="eyebrow" style={{ marginBottom: 0, letterSpacing: '0.06em' }}>
              {company.name}
            </span>
            {companies && companies.length > 1 && (
              <>
                <div className="topbar-divider" aria-hidden="true" />
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <select
                    className="company-select"
                    value={company?.id || ''}
                    onChange={e => onCompany(Number(e.target.value))}
                    aria-label="Select company"
                  >
                    {companies.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
          </>
        )}
      </div>

      <div className="topbar-right">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span
            style={{
              width: 6, height: 6, borderRadius: '50%',
              background: 'var(--status-healthy)',
              display: 'inline-block', flexShrink: 0
            }}
            aria-hidden="true"
          />
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 500 }}>
            All systems operational
          </span>
        </div>

        {user && (
          <div className="topbar-user">
            <div className="topbar-divider" aria-hidden="true" />
            <span className="topbar-email" title={user.email}>{user.email}</span>
            <button
              className="btn-ghost"
              onClick={logout}
              aria-label="Log out"
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <LogOut size={12} aria-hidden="true" />
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
