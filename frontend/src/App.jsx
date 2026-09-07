import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import { getCompanies, seedDemo } from './services/api';
import Overview from './pages/Overview';
import Shipments from './pages/Shipments';
import Demand from './pages/Demand';
import Inventory from './pages/Inventory';
import Suppliers from './pages/Suppliers';
import Anomalies from './pages/Anomalies';
import Simulator from './pages/Simulator';
import Recommendations from './pages/Recommendations';
import Models from './pages/Models';
import Data from './pages/Data';
import Login from './pages/Login';
import Register from './pages/Register';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider, useAuth } from './auth/AuthContext';

/* ── Brand Logo SVG Mark ─────────────────────────────────────── */
function BrandMark() {
  return (
    <div className="brand-logo" style={{ width: 40, height: 40, borderRadius: 10, margin: '0 auto 16px' }}>
      <svg style={{ position: 'relative', zIndex: 1, width: 20, height: 20 }} viewBox="0 0 14 14" fill="none">
        <path d="M7 1L12 4v6l-5 3L2 10V4l5-3z" stroke="#040810" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
        <path d="M7 5l3 1.75v3.5L7 12l-3-1.75V6.75L7 5z" fill="#040810" opacity="0.6"/>
      </svg>
    </div>
  );
}

function MainApp() {
  const { user, isAuthenticated } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [id, setId] = useState(Number(localStorage.getItem('supplyiq_company') || 0));
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = () => {
    // Only load companies if user is authenticated
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    getCompanies()
      .then(x => {
        setCompanies(x);

        // Use user's company_id as preference if available, else fallback to local storage / first company
        let defaultCompanyId = user?.company_id || id;
        if (!defaultCompanyId && x[0]) defaultCompanyId = x[0].id;

        // Enforce the user's company_id if they are not superuser
        if (user && !user.is_superuser && user.company_id) {
          defaultCompanyId = user.company_id;
        }

        setId(defaultCompanyId);
        localStorage.setItem('supplyiq_company', defaultCompanyId);
      })
      .catch(e => setErr(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [isAuthenticated, user]);

  const seed = () => {
    setLoading(true);
    seedDemo()
      .then(load)
      .catch(e => {
        setErr(e.response?.data?.detail || e.message);
        setLoading(false);
      });
  };

  const changeCompany = x => {
    // Prevent changing company if not superuser
    if (user && !user.is_superuser && user.company_id !== x) {
      return;
    }
    setId(x);
    localStorage.setItem('supplyiq_company', x);
  };

  if (loading) return (
    <div className="boot">
      <BrandMark />
      <h2>SupplyIQ</h2>
      <p>Starting intelligence layer…</p>
      <div className="spinner" style={{ marginTop: 8 }} aria-hidden="true" />
    </div>
  );

  if (isAuthenticated && !companies.length) return (
    <div className="boot">
      <BrandMark />
      <h2>No company data yet</h2>
      <p>Seed the realistic demo companies to start.</p>
      <button className="primary" onClick={seed}>Seed demo data</button>
      {err && <p className="error" style={{ maxWidth: 360 }}>{err}</p>}
    </div>
  );

  const company = companies.find(x => x.id === id) || companies[0];

  return (
    <div className="app">
      {isAuthenticated && <Sidebar />}
      <main
        className="main"
        style={{
          width: isAuthenticated ? `calc(100% - var(--sidebar-w))` : '100%',
          marginLeft: isAuthenticated ? 'var(--sidebar-w)' : '0'
        }}
      >
        {isAuthenticated && (
          <Topbar
            company={company}
            companies={user?.is_superuser ? companies : (company ? [company] : [])}
            onCompany={changeCompany}
          />
        )}
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Overview company={company} />} />
            <Route path="/shipments" element={<Shipments company={company} />} />
            <Route path="/demand" element={<Demand company={company} />} />
            <Route path="/inventory" element={<Inventory company={company} />} />
            <Route path="/suppliers" element={<Suppliers company={company} />} />
            <Route path="/anomalies" element={<Anomalies company={company} />} />
            <Route path="/simulator" element={<Simulator company={company} />} />
            <Route path="/recommendations" element={<Recommendations company={company} />} />
            <Route path="/models" element={<Models company={company} />} />
            <Route path="/data" element={<Data company={company} />} />
          </Route>
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <MainApp />
      </AuthProvider>
    </BrowserRouter>
  );
}
