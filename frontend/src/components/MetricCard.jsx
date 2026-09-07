export default function MetricCard({ label, value, sub, tone = '' }) {
  return (
    <div className={`metric${tone ? ' ' + tone : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{sub || 'Live analytics'}</small>
    </div>
  );
}
