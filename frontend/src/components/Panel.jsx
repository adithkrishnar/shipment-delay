export default function Panel({title,children,action}){return <section className="panel"><div className="panel-head"><h3>{title}</h3>{action}</div>{children}</section>}
