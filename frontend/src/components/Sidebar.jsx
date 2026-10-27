import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Boxes, Warehouse, TrendingUp, RefreshCw,
  SlidersHorizontal, FlaskConical, Sparkles, Grid3X3, UploadCloud, BrainCircuit
} from 'lucide-react';

const navGroups = [
  {
    label: 'Operations',
    links: [
      ['/', 'Overview', LayoutDashboard],
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
