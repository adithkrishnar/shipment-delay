export default function RiskBadge({risk}){return <span className={`risk risk-${String(risk||'LOW').toLowerCase()}`}>{risk}</span>}
