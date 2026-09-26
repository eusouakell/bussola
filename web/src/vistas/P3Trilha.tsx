// P3 · Trilha: criação, ajustes e meses acompanhados, na ordem em que
// aconteceram. Planejado, realizado e diferença vêm do `avancar_mes`; o
// medidor usa o percentual da meta que a ferramenta devolveu (FR-007).
import { dadosDe } from "../agente/envelope";
import { Icone } from "../componentes/base/Icone";
import { capitalizar, lista, num, txt } from "../componentes/cards/ler";
import { larguraMedidor } from "../componentes/cards/partes";
import { brl, mascararId, mesAbrev, meses, percentual } from "../formatacao/formatar";
import { R_AVANCAR } from "../simulado/textos";
import { statusMes, type EventoTrilha, type MesLido, type PlanoLido } from "./dados";
import { BotaoAcao, Fonte, SeloStatus, tomStatus } from "./partes";

interface Props {
  plano: PlanoLido;
  onEnviar: (texto: string) => void;
}

export function P3Trilha({ plano, onEnviar }: Props) {
  return (
    <section aria-label="P3Trilha" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <article className="glass-card enter" aria-label="Planejado × realizado, mês a mês" style={{ padding: 16, display: "flex", flexDirection: "column" }}>
        <span className="eyebrow" style={{ marginBottom: 12 }}>
          Planejado × realizado, mês a mês
        </span>
        <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {plano.trilha.map((evento) => (
            <Evento key={chaveEvento(evento)} evento={evento} plano={plano} />
          ))}
          <li className="tl-item last" style={{ paddingBottom: 0 }}>
            <span className="tl-dot now" aria-hidden="true" />
            <div className="tl-main" style={{ gap: 8 }}>
              <div className="tl-title" style={{ color: "var(--accent-ink)" }}>
                <span>PRÓXIMO MÊS</span>
              </div>
              <span className="tl-sub">Avance um mês para ver o planejado × realizado com os dados do extrato.</span>
              <BotaoAcao icone="avancar" onClick={() => onEnviar(R_AVANCAR)}>
                {R_AVANCAR}
              </BotaoAcao>
            </div>
          </li>
        </ol>
      </article>
    </section>
  );
}

function chaveEvento(e: EventoTrilha): string {
  return e.tipo === "mes" ? e.mes.chave : `${e.tipo}-${e.origem.chamadaId}`;
}

function Evento({ evento, plano }: { evento: EventoTrilha; plano: PlanoLido }) {
  if (evento.tipo === "mes") return <Mes mes={evento.mes} />;
  const dados = dadosDe(evento.origem.resposta);
  if (evento.tipo === "criacao") {
    const anomes = num(dados, "criado_em_anomes");
    const aceito = plano.criacao === evento.origem ? plano.consentimentos.criar_plano : undefined;
    const consentimento = aceito?.status === "aceito" ? aceito.consent_id : undefined;
    return (
      <li className="tl-item">
        <span className="tl-dot done" aria-hidden="true" />
        <div className="tl-main">
          <div className="tl-title">
            <span>{anomes ? `${mesAbrev(anomes).toUpperCase()} · PLANO CRIADO` : "PLANO CRIADO"}</span>
            <Fonte origem={evento.origem} compacto />
          </div>
          <span className="tl-sub num">
            {capitalizar(txt(dados, "cenario"))} · {brl(num(dados, "aporte_mensal"))}/mês · meta {brl(num(dados, "valor_alvo"))} em{" "}
            {meses(num(dados, "prazo_meses"))}
            {consentimento && (
              <>
                {" "}
                · autorizado <span className="mono">{mascararId(consentimento)}</span>
              </>
            )}
          </span>
        </div>
      </li>
    );
  }
  return (
    <li className="tl-item">
      <span className="tl-dot done" aria-hidden="true" />
      <div className="tl-main">
        <div className="tl-title">
          <span>PLANO AJUSTADO{txt(dados, "rota") ? ` · ROTA ${txt(dados, "rota")}` : ""}</span>
          <Fonte origem={evento.origem} compacto />
        </div>
        <span className="tl-sub num">
          {brl(num(dados, "aporte_mensal"))}/mês · {meses(num(dados, "prazo_meses"))} no total
        </span>
      </div>
    </li>
  );
}

function Mes({ mes }: { mes: MesLido }) {
  const d = mes.dados;
  const anomes = num(d, "anomes");
  const status = statusMes(txt(d, "status"));
  const desvio = num(d, "desvio");
  const pct = num(d, "percentual");
  const temRotas = lista(d, "rotas").length > 0;
  const dot = status === "desvio" ? "warn" : status ? "ok" : "done";
  const corDesvio = status === "desvio" ? "var(--warn)" : status === "folga" ? "var(--ok)" : "var(--ink-2)";
  return (
    <li className="tl-item" style={{ paddingBottom: 16 }}>
      <span className={`tl-dot ${dot}`} aria-hidden="true" />
      <div className="tl-main" style={{ gap: 6 }}>
        <div className="tl-title">
          <span>{mesAbrev(anomes).toUpperCase()}</span>
          {desvio !== undefined && (
            <span className="num" style={{ color: corDesvio }}>
              {desvio > 0 ? "+" : ""}
              {brl(desvio)}
            </span>
          )}
        </div>
        <div className="row-between" style={{ gap: 6 }}>
          <SeloStatus status={status} />
          <Fonte origem={mes.origem} compacto />
        </div>
        <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 12, rowGap: 2 }} className="small num">
          <dt>Planejado</dt>
          <dd style={{ margin: 0, textAlign: "right", fontWeight: 800 }}>{brl(num(d, "planejado"))}</dd>
          <dt>Realizado</dt>
          <dd style={{ margin: 0, textAlign: "right", fontWeight: 800, color: corDesvio }}>{brl(num(d, "realizado"))}</dd>
        </dl>
        {pct !== undefined && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div className={`meter ${tomStatus(status)}`} aria-hidden="true">
              <span style={{ width: larguraMedidor(pct) }} />
            </div>
            <span className="tl-sub num">
              {percentual(pct)} da meta · {brl(num(d, "acumulado"))} guardados
            </span>
          </div>
        )}
        {status === "desvio" && temRotas && (
          <span className="tl-sub" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Icone nome="recarregar" tamanho="sm" />
            Rota recalculada: as opções estão na conversa
          </span>
        )}
      </div>
    </li>
  );
}
