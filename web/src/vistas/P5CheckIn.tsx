// P5 · Check-in do mês: o aporte do plano, o progresso já devolvido pelas
// ferramentas e as ações que o agente entende. Nada é registrado aqui: os
// botões só mandam texto à conversa, e o realizado vem dos dados do mês.
import { Disclaimer } from "../componentes/base/Disclaimer";
import { larguraMedidor } from "../componentes/cards/partes";
import { brl, mesAbrev, percentual } from "../formatacao/formatar";
import { R_AVANCAR, R_LEMBRETES, R_STATUS } from "../sessao/sugestoes-padrao";
import { doProgresso, type PlanoLido } from "./dados";
import { BotaoAcao, Fonte, Fontes, NotaUltimoMes, tomStatus } from "./partes";

interface Props {
  plano: PlanoLido;
  ateAnomes: number | undefined;
  onEnviar: (texto: string) => void;
}

export function P5CheckIn({ plano, ateAnomes, onEnviar }: Props) {
  const acumulado = doProgresso(plano, "acumulado");
  const pct = doProgresso(plano, "percentual");
  const lembretesAtivos = plano.lembretes?.status === "aceito";

  return (
    <section aria-label="P5CheckIn" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <header style={{ display: "flex", flexDirection: "column", gap: 4, padding: "4px 6px 0" }}>
        <span className="eyebrow">{ateAnomes ? `Check-in mensal · dados até ${mesAbrev(ateAnomes)}` : "Check-in mensal"}</span>
        <h2 style={{ margin: 0, fontSize: 26, lineHeight: "32px", fontWeight: 900, letterSpacing: "-0.01em" }}>
          Separar <span className="num">{brl(plano.aporte.valor)}</span> neste mês
        </h2>
        <div className="row-between">
          <span className="small">{plano.descricao ? `Objetivo: ${plano.descricao}` : "Aporte mensal do plano"}</span>
          <Fonte origem={plano.aporte.origem} compacto />
        </div>
      </header>

      <article className="glass-card enter" aria-label="Progresso do check-in" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
        {acumulado.valor !== undefined ? (
          <>
            <div className="row-between">
              <span className="small num" style={{ fontWeight: 800, color: "var(--ink)" }}>
                {brl(acumulado.valor)} de {brl(plano.meta.valor)}
              </span>
              <Fontes origens={[acumulado.origem, plano.meta.origem]} compacto />
            </div>
            <div className={`meter lg ${tomStatus(plano.ultimoStatus)}`} aria-hidden="true">
              <span style={{ width: larguraMedidor(pct.valor) }} />
            </div>
            <span className="small num">{percentual(pct.valor)} da meta</span>
          </>
        ) : (
          <span className="small">
            Ainda não há mês acompanhado. Ao avançar um mês, a Bússola compara o planejado com o realizado dos seus dados.
          </span>
        )}
      </article>

      <NotaUltimoMes plano={plano} />

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <BotaoAcao primario icone="avancar" onClick={() => onEnviar(R_AVANCAR)}>
          {R_AVANCAR}
        </BotaoAcao>
        <BotaoAcao icone="grafico" onClick={() => onEnviar(R_STATUS)}>
          {R_STATUS}
        </BotaoAcao>
        {!lembretesAtivos && (
          <BotaoAcao icone="sino" onClick={() => onEnviar(R_LEMBRETES)}>
            {R_LEMBRETES}
          </BotaoAcao>
        )}
        <Disclaimer icone="info" centralizado>
          O realizado vem dos seus dados do mês. A Bússola não movimenta dinheiro.
        </Disclaimer>
      </div>
    </section>
  );
}
