// Peças comuns dos cards: cabeçalho (tag + fonte) e caixa de KPI.
import type { CSSProperties, ReactNode } from "react";
import { avisosDe, fonteDe } from "../../agente/envelope";
import type { RespostaFerramenta, TagMensagem } from "../../agente/tipos";
import { ChipFonte } from "../base/ChipFonte";
import { Tag } from "../base/Tag";

interface CabecalhoProps {
  tag: TagMensagem;
  textoTag?: string;
  resposta?: RespostaFerramenta;
  /** Conteúdo extra à direita, no lugar do chip de fonte. */
  direita?: ReactNode;
}

export function CabecalhoCard({ tag, textoTag, resposta, direita }: CabecalhoProps) {
  return (
    <div className="row-between">
      <Tag tipo={tag} texto={textoTag} />
      {direita ?? <ChipFonte fonte={fonteDe(resposta)} avisos={avisosDe(resposta)} />}
    </div>
  );
}

interface KpiProps {
  rotulo: string;
  valor: ReactNode;
  sufixo?: string;
  tom?: "warn" | "ok";
  estilo?: CSSProperties;
}

export function Kpi({ rotulo, valor, sufixo, tom, estilo }: KpiProps) {
  const cor = tom ? `var(--${tom})` : undefined;
  const fundo = tom ? `var(--${tom}-soft)` : undefined;
  return (
    <div className="kpi-box" style={{ background: fundo, ...estilo }}>
      <span className="kpi-label" style={{ color: cor }}>
        {rotulo}
      </span>
      <span className="kpi" style={{ color: cor }}>
        <span className="kpi-valor">{valor}</span>
        {sufixo &&<span style={{ fontSize: 15, fontWeight: 800, color: cor ?? "var(--ink-2)" }}>{sufixo}</span>}
      </span>
    </div>
  );
}

/** Largura visual do medidor a partir de um percentual já calculado pela ferramenta. */
export function larguraMedidor(pontos: number | undefined): string {
  if (typeof pontos !== "number" || Number.isNaN(pontos)) return "0%";
  return `${Math.min(100, Math.max(1, pontos))}%`;
}
