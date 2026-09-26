/** Fundo dinâmico: as cores dos blobs seguem `data-estado` no `.app`. */
export function Ambiente() {
  return (
    <div className="ambient" aria-hidden="true">
      <div className="blob b1" />
      <div className="blob b2" />
      <div className="blob b3" />
    </div>
  );
}
