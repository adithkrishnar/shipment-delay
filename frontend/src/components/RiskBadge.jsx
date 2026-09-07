export default function RiskBadge({ risk }) {
  const tier = String(risk || 'LOW').toLowerCase();
  return (
    <span className={`risk risk-${tier}`} aria-label={`Risk: ${risk}`}>
      {String(risk || 'LOW').toUpperCase()}
    </span>
  );
}
