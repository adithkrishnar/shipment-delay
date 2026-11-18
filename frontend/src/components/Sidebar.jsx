import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Boxes, Warehouse, TrendingUp, RefreshCw,
  SlidersHorizontal, FlaskConical, Sparkles, Grid3X3, UploadCloud, BrainCircuit, Truck
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';

export default function Sidebar() {
  const { user } = useAuth();
  const participantRole = user?.participant_role || (user?.role === 'transporter' ? 'transporter' : 'company');
  const isSuperuser = Boolean(user?.is_superuser);

  let navGroups = [];

  if (participantRole === 'transporter') {
    navGroups = [
      {
        label: 'Carrier Fleet Operations',
        links: [
          ['/transporter', 'Assigned Shipments & Corridors', Truck],
        ]
      }
    ];
  } else if (participantRole === 'sender' && !isSuperuser) {
    navGroups = [
      {
        label: 'Outbound Operations',
        links: [
          ['/', 'Dispatch Operations Cockpit', LayoutDashboard],
          ['/shipments', 'Outbound Shipments & Linehaul', Truck],
        ]
      },
      {
        label: 'Corridor Analytics',
        links: [
          ['/delay-simulator', 'Transit Delay Simulator', SlidersHorizontal],
          ['/what-if', 'Corridor What-If Lab', FlaskConical],
        ]
      },
      {
        label: 'System & Enterprise',
        links: [
          ['/data', 'Enterprise Data & Shipments', UploadCloud],
          ['/models', 'ML Models & Route Quality', BrainCircuit],
        ]
      }
    ];
  } else if (participantRole === 'receiver' && !isSuperuser) {
    navGroups = [
      {
        label: 'Warehouse Operations',
        links: [
          ['/', 'Warehouse Receiving Tower', LayoutDashboard],
          ['/inventory', 'Inventory Explorer', Boxes],
          ['/shipments', 'Inbound Freight & Goods Inward', Truck],
          ['/suppliers', 'Supplier Intelligence', Warehouse],
          ['/replenishment', 'Replenishment Planning', RefreshCw],
        ]
      },
      {
        label: 'Inventory Intelligence',
        links: [
          ['/demand', 'Consumption & Demand Forecasts', TrendingUp],
          ['/delay-simulator', 'Stockout Risk Simulator', SlidersHorizontal],
          ['/recommendations', 'Prescriptive Action Center', Sparkles],
          ['/insights', 'ABC-XYZ Inventory Insights', Grid3X3],
        ]
      },
      {
        label: 'System',
        links: [
          ['/data', 'Warehouse Data & Imports', UploadCloud],
          ['/models', 'Forecasting & Risk Models', BrainCircuit],
        ]
      }
    ];
  } else {
    // Administrator / Superuser view spanning all capabilities
    navGroups = [
      {
        label: 'Operations',
        links: [
          ['/', 'Overview', LayoutDashboard],
          ['/shipments', 'Shipments & In-Transit', Truck],
          ['/inventory', 'Inventory Explorer', Boxes],
          ['/products', 'Products & Warehouses', Warehouse],
          ['/demand', 'Demand Forecasts', TrendingUp],
          ['/replenishment', 'Replenishment', RefreshCw],
        ]
      },
      {
        label: 'Decision Support',
        links: [
          ['/delay-simulator', 'Delay Simulator', SlidersHorizontal],
          ['/what-if', 'What-If Lab', FlaskConical],
          ['/recommendations', 'Action Center', Sparkles],
          ['/insights', 'Inventory Insights', Grid3X3],
        ]
      },
      {
        label: 'System',
        links: [
          ['/data', 'Data & Imports', UploadCloud],
          ['/models', 'Models & Quality', BrainCircuit],
        ]
      }
    ];
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-logo" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7 1L12 4v6l-5 3L2 10V4l5-3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
          </svg>
        </div>
        <div className="brand-name">SUPPLYIQ</div>
      </div>

      <nav className="sidebar-nav" aria-label="Main navigation">
        {navGroups.map((group) => (
          <div className="nav-section" key={group.label}>
            <div className="nav-section-label">{group.label}</div>
            {group.links.map(([to, label, Icon]) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                aria-label={label}
              >
                <Icon size={18} className="nav-icon" aria-hidden="true" />
                <span className="nav-label">{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
