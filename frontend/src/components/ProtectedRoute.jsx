import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function ProtectedRoute() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="boot">
        <div className="brand-logo" style={{ width: 40, height: 40, borderRadius: 10, margin: '0 auto 16px' }}>
          <svg style={{ position: 'relative', zIndex: 1, width: 20, height: 20 }} viewBox="0 0 14 14" fill="none">
            <path d="M7 1L12 4v6l-5 3L2 10V4l5-3z" stroke="#040810" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
            <path d="M7 5l3 1.75v3.5L7 12l-3-1.75V6.75L7 5z" fill="#040810" opacity="0.6"/>
          </svg>
        </div>
        <h2>SupplyIQ</h2>
        <p>Verifying authentication…</p>
        <div className="spinner" style={{ marginTop: 8 }} aria-hidden="true" />
      </div>
    );
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
