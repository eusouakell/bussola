// P2 · Meu plano: meta, aporte, prazo, progresso e meses acompanhados, cada
// número com a fonte do envelope de onde veio (US5). Só leitura (FR-024).
import { Icone } from "../componentes/base/Icone";
import { larguraMedidor } from "../componentes/cards/partes";
import { brl, meses, numero, percentual } from "../formatacao/formatar";
import { R_AVANCAR } from "../sessao/sugestoes-padrao";
import { doProgresso, type PlanoLido } from "./dados";
import { BotaoAcao, Fonte, KpiFonte, NotaUltimoMes, SeloStatus, tomStatus } from "./partes";
import type { NomeVista } from "./Vistas";

interface Props {
  plano: PlanoLido;
  onVista: (v: NomeVista) => void;
  onEnviar: (texto: string) => void;
}

export function P2MeuPlano({ plano, onVista, onEnviar }: Props) {
  const acumulado = doProgresso(plano, "acumulado");
  const pct = doProgresso(plano, "percentual");
  const restante = doProgresso(plano, "restante");
  const decorridos = doProgresso(plano, "meses_decorridos");
  const temProgresso = acumulado.valor !== undefined;

  return (
    <section aria-label="P2MeuPlano" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <article className="glass-card card-pad enter" aria-label="Progresso do plano" style={{ gap: 14 }}>
        <div className="row-between" style={{ alignItems: "flex-start" }}>
          <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
            <span className="eyebrow">Objetivo</span>
            <span style={{ fontSize: 20, lineHeight: "26px", fontWeight: 900 }}>{plano.descricao ?? "Seu plano"}</span>
          </div>
          <SeloStatus status={plano.ultimoStatus} />
        </div>

        {temProgresso ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span className="kpi-label">Guardado até agora</span>
            <span className="kpi num">{brl(acumulado.valor)}</span>
            {plano.meta.valor !== undefined && <span className="small num">de {brl(plano.meta.valor)}</span>}
            <div className={`meter lg ${tomStatus(plano.ultimoStatus)}`} aria-hidden="true">
              <span style={{ width: larguraMedidor(pct.valor) }} />
            </div>
            <div className="row-between">
              <span className="small num">
                {percentual(pct.valor)} da meta
                {restante.valor !== undefined && <> · faltam {brl(restante.valor)}</>}
              </span>
              <Fonte origem={plano.progresso} />
            </div>
          </div>
        ) : (
          <div className="note note-info" style={{ fontSize: 14.5, lineHeight: "20px", padding: "10px 12px" }}>
            <Icone nome="info" />
            <span>Nenhum mês acompanhado ainda. Avance um mês na conversa para ver o planejado × realizado.</span>
          </div>
        )}

        <div className="grid-kpi">
          <KpiFonte rotulo="Meta" valor={brl(plano.meta.valor)} origem={plano.meta.origem} />
          <KpiFonte rotulo="Aporte" valor={brl(plano.aporte.valor)} sufixo="/mês" origem={plano.aporte.origem} />
          <KpiFonte rotulo="Prazo" valor={meses(plano.prazo.valor)} origem={plano.prazo.origem} />
        </div>
        {decorridos.valor !== undefined && (
          <div className="row-between">
            <span className="small">
              Meses acompanhados: <strong className="num">{numero(decorridos.valor)}</strong>
            </span>
            <Fonte origem={decorridos.origem} compacto />
          </div>
        )}
      </article>

      <article className="glass-card enter" aria-label="Aporte do plano" style={{ padding: "14px 16px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span className="st" aria-hidden="true" style={{ width: 44, height: 44, borderRadius: 14, background: "var(--accent-soft)", color: "var(--accent-ink)" }}>
          <Icone nome="calendario" />
        </span>
        <div style={{ display: "flex", flexDirection: "column", flex: "1 1 auto", minWidth: 0 }}>
          <span className="kpi-label">Aporte mensal do plano</span>
          <span className="num" style={{ fontSize: 22, fontWeight: 900 }}>
            {brl(plano.aporte.valor)}
          </span>
        </div>
        <Fonte origem={plano.aporte.origem} compacto />
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => onVista("check-in")}>
          Check-in
        </button>
      </article>

      {plano.ultimoMes ? (
        <NotaUltimoMes plano={plano} />
      ) : (
        <BotaoAcao icone="avancar" onClick={() => onEnviar(R_AVANCAR)}>
          {R_AVANCAR}
        </BotaoAcao>
      )}
    </section>
  );
}
