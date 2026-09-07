export default function Panel({ title, children, action }) {
  return (
    <section className="panel">
      {title && (
        <div className="panel-head">
          <h3>{title}</h3>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
