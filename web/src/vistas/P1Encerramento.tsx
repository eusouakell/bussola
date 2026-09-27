// P1 · Encerramento: a jornada virou um plano. Mostra o que o cliente leva,
// com os números do plano criado (ou ajustado) e o estado dos lembretes.
import type { ReactNode } from "react";
import { Icone, type NomeIcone } from "../componentes/base/Icone";
import { brl, dataHora, mascararId, meses } from "../formatacao/formatar";
import { R_LEMBRETES } from "../sessao/sugestoes-padrao";
import type { PlanoLido } from "./dados";
import { BotaoAcao, Fontes } from "./partes";
import type { NomeVista } from "./Vistas";

/** Texto que o agente (real ou simulado) entende como pedido de ajuda para um novo objetivo. */
export const R_OUTRO_OBJETIVO = "Me ajuda a começar outro objetivo";

interface Props {
  plano: PlanoLido;
  onVista: (v: NomeVista) => void;
  onEnviar: (texto: string) => void;
}

export function P1Encerramento({ plano, onVista, onEnviar }: Props) {
  const lembretes = plano.lembretes;
  const lembretesAtivos = lembretes?.status === "aceito";
  const resumoPlano = [
    plano.aporte.valor !== undefined ? `${brl(plano.aporte.valor)}/mês` : null,
    plano.meta.valor !== undefined ? `meta ${brl(plano.meta.valor)}` : null,
    plano.prazo.valor !== undefined ? `em ${meses(plano.prazo.valor)}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section aria-label="P1Encerramento" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {lembretesAtivos && (
        <div className="receipt ok" role="status" style={{ padding: "10px 12px", fontSize: 14 }}>
          <span className="st" aria-hidden="true" style={{ background: "var(--ok)", color: "#fff" }}>
            <Icone nome="check" tamanho="sm" traco={3} />
          </span>
          <span>
            Lembretes mensais autorizados
            {lembretes.ts !== undefined && <> · {dataHora(lembretes.ts)}</>} ·{" "}
            <span className="mono" style={{ fontWeight: 600 }}>
              {mascararId(lembretes.consent_id)}
            </span>
          </span>
        </div>
      )}

      <article className="glass-consent enter" aria-label="Entrega da jornada" style={{ padding: "18px 16px 16px", display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="brand-mark" aria-hidden="true" style={{ width: 44, height: 44, borderRadius: 14 }}>
            <Icone nome="bussola" />
          </span>
          <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
            <span className="eyebrow" style={{ color: "var(--ok)" }}>
              Jornada concluída
            </span>
            <span style={{ fontSize: 20, lineHeight: "26px", fontWeight: 900 }}>Sua jornada virou um plano</span>
          </div>
        </div>
        <p className="prose" style={{ fontSize: 15.5, lineHeight: "22px", color: "var(--ink-2)" }}>
          A partir de agora eu acompanho sua rota até a meta{plano.descricao ? ` (${plano.descricao})` : ""}. Isto é o que você
          leva:
        </p>

        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
          <Entrega icone="alvo" cor="accent" titulo="Plano ativo" direita={<Fontes origens={[plano.aporte.origem, plano.meta.origem, plano.prazo.origem]} compacto />}
          >
            <span className="num">{resumoPlano || `plano ${mascararId(plano.planoId)}`}</span>
          </Entrega>
          <Entrega icone="calendario" cor="diag" titulo="Check-in todo mês">
            {lembretesAtivos ? "Lembrete mensal ativo e planejado × realizado do mês" : "Planejado × realizado do mês, com lembrete se você quiser"}
          </Entrega>
          <Entrega icone="trilha" cor="warn" titulo="Rota que se recalcula">
            Saiu da trilha? Eu mostro opções para voltar
          </Entrega>
          <Entrega icone="lista" cor="ok" titulo="Resumo com fontes e autorizações">
            Cada número mostra de onde veio
          </Entrega>
        </ul>

        <BotaoAcao primario icone="alvo" onClick={() => onVista("meu-plano")}>
          Abrir Meu plano
        </BotaoAcao>
        {!lembretesAtivos && (
          <BotaoAcao icone="sino" onClick={() => onEnviar(R_LEMBRETES)}>
            {R_LEMBRETES}
          </BotaoAcao>
        )}
        <BotaoAcao onClick={() => onEnviar(R_OUTRO_OBJETIVO)}>Começar outro objetivo</BotaoAcao>
      </article>
    </section>
  );
}

const CORES: Record<string, { fundo: string; tinta: string }> = {
  accent: { fundo: "var(--accent-soft)", tinta: "var(--accent-ink)" },
  diag: { fundo: "var(--tag-diag-bg)", tinta: "var(--tag-diag)" },
  warn: { fundo: "var(--warn-soft)", tinta: "var(--warn)" },
  ok: { fundo: "var(--ok-soft)", tinta: "var(--ok)" },
};

interface EntregaProps {
  icone: NomeIcone;
  cor: keyof typeof CORES;
  titulo: string;
  children: ReactNode;
  direita?: ReactNode;
}

function Entrega({ icone, cor, titulo, children, direita }: EntregaProps) {
  const c = CORES[cor];
  return (
    <li className="check-item" style={{ padding: "11px 12px", alignItems: "center" }}>
      <span className="st" aria-hidden="true" style={{ width: 34, height: 34, borderRadius: 11, background: c.fundo, color: c.tinta }}>
        <Icone nome={icone} tamanho="sm" />
      </span>
      <span style={{ display: "flex", flexDirection: "column", flex: "1 1 auto", minWidth: 0 }}>
        <span style={{ fontSize: 15, fontWeight: 900 }}>{titulo}</span>
        <span className="small" style={{ fontSize: 13.5 }}>
          {children}
        </span>
      </span>
      {direita}
    </li>
  );
}
