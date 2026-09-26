import { Icone } from "./Icone";

interface Props {
  avisos: string[] | undefined;
}

const SIMULADA = /^Resposta simulada pelo front; regravar após o ciclo (\d{3})$/;

/** `avisos` do envelope como alerta âmbar, nunca como erro (FR-009). */
export function Avisos({ avisos }: Props) {
  if (!avisos || avisos.length === 0) return null;
  const simulada = avisos.map((a) => SIMULADA.exec(a)).find(Boolean);
  const demais = avisos.filter((a) => !SIMULADA.test(a));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-start" }} aria-label="Avisos da consulta">
      {demais.map((aviso) => (
        <div
          key={aviso}
          className="note note-warn"
          style={{ fontSize: 14, lineHeight: "19px", padding: "9px 12px", alignSelf: "stretch" }}
        >
          <Icone nome="alerta" />
          <span>{aviso}</span>
        </div>
      ))}
      {simulada && (
        <span className="badge badge-warn" title={simulada[0]} style={{ height: 24, fontSize: 12 }}>
          <Icone nome="frasco" tamanho="sm" />
          Resposta simulada pelo front · ciclo {simulada[1]}
        </span>
      )}
    </div>
  );
}
