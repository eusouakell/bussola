// Stepper da jornada (FR-005): reflete `estado_jornada` do state da sessão.
import { useState } from "react";
import { ESTADOS_JORNADA, type EstadoJornada } from "../../agente/tipos";
import { Icone } from "../base/Icone";

export const NOMES_ESTADO: Record<EstadoJornada, string> = {
  OBJETIVO: "Objetivo",
  ENTENDER: "Entender",
  ANTECIPAR: "Antecipar",
  ORIENTAR: "Orientar",
  AGIR: "Agir",
  ACOMPANHAR: "Acompanhar",
};

const DESCRICOES: Record<EstadoJornada, string> = {
  OBJETIVO: "Você conta o que quer conquistar.",
  ENTENDER: "Analiso renda, gastos, sobra e parcelas.",
  ANTECIPAR: "Simulo quanto guardar e em quanto tempo.",
  ORIENTAR: "Comparo caminhos e recomendo um.",
  AGIR: "Crio o plano com a sua autorização.",
  ACOMPANHAR: "Acompanho mês a mês e recalculo a rota.",
};

export type SituacaoPasso = "done" | "now" | "next";

export interface Passo {
  estado: EstadoJornada;
  nome: string;
  numero: number;
  situacao: SituacaoPasso;
}

export function passosJornada(atual: EstadoJornada | undefined): Passo[] {
  const indice = ESTADOS_JORNADA.indexOf(atual ?? "OBJETIVO");
  return ESTADOS_JORNADA.map((estado, i) => ({
    estado,
    nome: NOMES_ESTADO[estado],
    numero: i + 1,
    situacao: i < indice ? "done" : i === indice ? "now" : "next",
  }));
}

interface Props {
  atual: EstadoJornada | undefined;
}

export function StepperJornada({ atual }: Props) {
  const passos = passosJornada(atual);
  const agora = passos.find((p) => p.situacao === "now") ?? passos[0];
  return (
    <nav className="glass-chrome stepper" aria-label={`Jornada: ${agora.nome}`}>
      <ol>
        {passos.map((p, i) => (
          <li key={p.estado} className="stepper-item" style={{ flex: i < passos.length - 1 ? "1 1 0" : "0 0 auto" }}>
            <div className={`wp ${p.situacao}`} aria-current={p.situacao === "now" ? "step" : undefined}>
              <span className="dot">
                {p.situacao === "done" ? <Icone nome="check" tamanho="sm" traco={3} /> : p.numero}
              </span>
              <span className="lbl">{p.nome}</span>
              <span className="sr-only">
                {p.situacao === "done" ? " (concluída)" : p.situacao === "now" ? " (etapa atual)" : " (próxima)"}
              </span>
            </div>
            {i < passos.length - 1 && <span className={p.situacao === "done" ? "rail done" : "rail"} />}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** Versão compacta do mobile: "N/6 · Estado", expande a lista das 6 etapas. */
export function StepperCompacto({ atual }: Props) {
  const [aberto, setAberto] = useState(false);
  const passos = passosJornada(atual);
  const agora = passos.find((p) => p.situacao === "now") ?? passos[0];
  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        className="step-compact"
        aria-expanded={aberto}
        aria-label={`Jornada: ${agora.nome}, etapa ${agora.numero} de 6. Toque para ver as 6 etapas`}
        onClick={() => setAberto((a) => !a)}
      >
        <span className="n">{agora.numero}/6</span>
        {agora.nome}
        <span className="step-tracos" aria-hidden="true">
          {passos.map((p) => (
            <span
              key={p.estado}
              style={{
                width: 10,
                height: 4,
                borderRadius: 2,
                background: p.situacao === "done" ? "var(--ink-2)" : p.situacao === "now" ? "var(--accent)" : "var(--line-strong)",
              }}
            />
          ))}
        </span>
        <Icone nome="chevronBaixo" tamanho="sm" estilo={{ transform: aberto ? "rotate(180deg)" : undefined }} />
      </button>
      {aberto && (
        <ol className="popover glass-card" aria-label="Etapas da jornada" style={{ left: 0, right: "auto", margin: 0, listStyle: "none" }}>
          {passos.map((p, i) => (
            <li key={p.estado} className={i === passos.length - 1 ? "tl-item last" : "tl-item"}>
              <span className={`tl-dot ${p.situacao}`} />
              <div className="tl-main">
                <div className="tl-title">
                  <span>
                    {p.numero}. {p.nome}
                  </span>
                  <span className="mono" style={{ color: "var(--ink-3)" }}>
                    {p.situacao === "done" ? "concluída" : p.situacao === "now" ? "agora" : "—"}
                  </span>
                </div>
                <span className="tl-sub">{DESCRICOES[p.estado]}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
