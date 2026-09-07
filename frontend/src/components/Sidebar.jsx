import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Ship, TrendingUp, Boxes, Factory,
  TriangleAlert, SlidersHorizontal, Sparkles, UploadCloud, BrainCircuit
} from 'lucide-react';

const navGroups = [
  {
    label: 'Intelligence',
    links: [
      ['/', 'Overview', LayoutDashboard],
      ['/shipments', 'Shipments', Ship],
      ['/demand', 'Demand Forecast', TrendingUp],
      ['/inventory', 'Inventory', Boxes],
      ['/suppliers', 'Suppliers', Factory],
      ['/anomalies', 'Anomalies', TriangleAlert],
    ]
  },
  {
    label: 'Tools',
    links: [
      ['/simulator', 'What-If Simulator', SlidersHorizontal],
      ['/recommendations', 'AI Recommendations', Sparkles],
    ]
  },
  {
    label: 'Operations',
    links: [
      ['/data', 'Data Management', UploadCloud],
      ['/models', 'Model Center', BrainCircuit],
    ]
  }
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-logo" aria-hidden="true">
          <svg className="brand-logo-mark" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7 1L12 4v6l-5 3L2 10V4l5-3z" stroke="#040810" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
            <path d="M7 5l3 1.75v3.5L7 12l-3-1.75V6.75L7 5z" fill="#040810" opacity="0.6"/>
          </svg>
        </div>
        <div className="brand-text">
          <div className="brand-name">SupplyIQ</div>
          <div className="brand-tagline">Intelligence Platform</div>
        </div>
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
                <Icon size={16} className="nav-icon" aria-hidden="true" />
                <span className="nav-label">{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-content">
          <span className="status-dot" aria-hidden="true" />
          <span className="sidebar-status-text">Systems operational</span>
        </div>
      </div>
    </aside>
  );
}
