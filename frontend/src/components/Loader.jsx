export default function Loader() {
  return (
    <div className="loader" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <span>Loading intelligence…</span>
    </div>
  );
}
