interface Props {
  opcoes: string[];
  onEscolher: (texto: string) => void;
  desabilitado?: boolean;
}

/** Respostas rápidas (`customMetadata.bussola.respostas_rapidas`): enviam o texto como mensagem. */
export function RespostasRapidas({ opcoes, onEscolher, desabilitado }: Props) {
  if (opcoes.length === 0) return null;
  return (
    <div role="group" aria-label="Respostas rápidas" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {opcoes.map((texto) => (
        <button key={texto} type="button" className="qr" disabled={desabilitado} onClick={() => onEscolher(texto)}>
          {texto}
        </button>
      ))}
    </div>
  );
}
