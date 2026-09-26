/** Card em carregamento (E5): aparece enquanto as consultas do turno rodam. */
export function Skeleton() {
  return (
    <article className="glass-card card-pad" aria-busy="true" aria-label="Carregando resultado" style={{ gap: 12 }}>
      <div className="row-between">
        <span className="sk" style={{ width: 118, height: 28, borderRadius: 999 }} />
        <span className="sk" style={{ width: 150, height: 28, borderRadius: 999 }} />
      </div>
      <span className="sk" style={{ width: "100%", height: 72, borderRadius: 16 }} />
      <div className="grid-2" style={{ gap: 8 }}>
        <span className="sk" style={{ height: 58, borderRadius: 14 }} />
        <span className="sk" style={{ height: 58, borderRadius: 14 }} />
      </div>
    </article>
  );
}
