import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Ship, TrendingUp, Boxes, Factory,
  TriangleAlert, SlidersHorizontal, Sparkles, UploadCloud, BrainCircuit
} from 'lucide-react';

const navGroups = [
  {
    label: 'Operations',
    links: [
      ['/', 'Overview', LayoutDashboard],
      ['/shipments', 'Shipments', Ship],
      ['/demand', 'Demand', TrendingUp],
      ['/inventory', 'Inventory', Boxes],
      ['/suppliers', 'Suppliers', Factory],
      ['/anomalies', 'Anomalies', TriangleAlert],
    ]
  },
  {
    label: 'Decision Support',
    links: [
      ['/simulator', 'Simulator', SlidersHorizontal],
      ['/recommendations', 'Action Center', Sparkles],
    ]
  },
  {
    label: 'System',
    links: [
      ['/data', 'Data Input', UploadCloud],
      ['/models', 'Models', BrainCircuit],
    ]
  }
];

export default function Sidebar() {
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
