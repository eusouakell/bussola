// Comparação de cenários (ORIENTAR): três caminhos lado a lado, selo
// destaque contextualizado (metadado do agente ou regra R9) e campo "Outro caminho".
import { useId, useState, type FormEvent } from "react";
import { avisosDe, dadosDe } from "../../agente/envelope";
import type { Dados } from "../../agente/tipos";
import { brl, fracaoPercentual, meses } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { DISCLAIMER_SIMULACAO, Disclaimer } from "../base/Disclaimer";
import { Icone } from "../base/Icone";
import { bool, capitalizar, lista, num, obj, textos, txt } from "./ler";
import { CabecalhoCard } from "./partes";

/** R9: metadado `recomendado`; sem ele, o viável de menor % da sobra. */
export function cenarioRecomendado(cenarios: Dados[], metadado?: string): string | undefined {
  if (metadado && cenarios.some((c) => c.nome === metadado)) return metadado;
  const viaveis = cenarios.filter((c) => c.viavel === true && typeof c.pct_capacidade === "number");
  viaveis.sort((a, b) => (a.pct_capacidade as number) - (b.pct_capacidade as number));
  return viaveis[0] ? txt(viaveis[0], "nome") : undefined;
}

interface CenarioProps {
  cenario: Dados;
  recomendado: boolean;
  escolhido: boolean;
  bloqueado: boolean;
  prazoObjetivo?: number;
  onEscolher: (nome: string) => void;
}

export function CardCenario({ cenario, recomendado, escolhido, bloqueado, prazoObjetivo, onEscolher }: CenarioProps) {
  const nome = txt(cenario, "nome") ?? "cenário";
  const pct = num(cenario, "pct_capacidade");
  const viavel = bool(cenario, "viavel");
  const prazo = num(cenario, "prazo_meses");
  const cortes = lista(cenario, "cortes_sugeridos");
  const economiaAdicional = cortes.reduce((total, corte) => total + (num(corte, "valor_mensal") ?? 0), 0);
  const aporte = num(cenario, "aporte_mensal");
  const aporteBase = aporte !== undefined ? aporte - economiaAdicional : undefined;
  const sobraBase = pct !== undefined && pct > 0 && aporteBase !== undefined ? aporteBase / pct : undefined;
  const proporcaoTotal = sobraBase && aporte !== undefined ? aporte / sobraBase : undefined;
  // Percentual-base e aporte total não são equivalentes quando há economias adicionais.
  const tradeOffs = textos(cenario, "trade_offs").filter(
    (texto) => economiaAdicional === 0 || !/^Compromete \d+% da sobra/i.test(texto),
  );
  const noPrazo = prazoObjetivo !== undefined && prazo !== undefined ? prazo <= prazoObjetivo : undefined;
  const condicoesAtendidas = viavel !== false && noPrazo !== false;
  const classes = ["glass-card", "cen", "enter", recomendado ? "rec" : ""].filter(Boolean).join(" ");
  return (
    <article className={classes} aria-label={`Cenário ${capitalizar(nome)}${recomendado ? ", em destaque" : ""}`}>
      {recomendado && (
        <span className="rec-flag">
          <Icone nome="estrela" tamanho="sm" />
          {economiaAdicional > 0 ? "Exige mudanças no orçamento" : "Caminho em destaque"}
        </span>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <h3 className="t-title">{capitalizar(nome)}</h3>
        <span className="small num">{fracaoPercentual(proporcaoTotal ?? pct)} da sobra típica {economiaAdicional > 0 ? "no total" : ""}</span>
      </div>
      <div className={recomendado ? "meter accent" : "meter"} aria-hidden="true">
        <span style={{ width: (proporcaoTotal ?? pct) !== undefined ? `${Math.min(100, (proporcaoTotal ?? pct ?? 0) * 100)}%` : "0%" }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span className="kpi num">
          {brl(num(cenario, "aporte_mensal"))}
          <span style={{ fontSize: 15, fontWeight: 800, color: "var(--ink-2)" }}>/mês</span>
        </span>
        <span className="small num">{meses(prazo)} até a meta</span>
      </div>
      {economiaAdicional > 0 && aporteBase !== undefined && (
        <div className="note note-info" style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14, lineHeight: "20px", padding: "12px" }}>
          <strong>Cortes propostos: {brl(economiaAdicional)}/mês</strong>
          <span>Essas economias ainda precisam acontecer.</span>
          <details>
            <summary style={{ fontWeight: 750, cursor: "pointer" }}>Como se forma o aporte</summary>
            <div style={{ display: "grid", gap: 4, marginTop: 8 }}>
              <span className="num">{brl(aporteBase)} da sobra típica + {brl(economiaAdicional)} em cortes.</span>
              {proporcaoTotal !== undefined && <span>O total usa cerca de <strong className="num">{fracaoPercentual(proporcaoTotal)}</strong> da sobra típica.</span>}
            </div>
          </details>
        </div>
      )}
      {viavel !== undefined && (
        <span className={condicoesAtendidas ? "badge badge-ok" : "badge badge-warn"} style={{ alignSelf: "flex-start" }}>
          <Icone nome={condicoesAtendidas ? "check" : "alerta"} tamanho="sm" traco={condicoesAtendidas ? 3 : undefined} />
          {noPrazo === false
            ? `Após o prazo desejado de ${meses(prazoObjetivo)}`
            : viavel === false
              ? "Rever viabilidade financeira"
              : noPrazo === true
                ? "Dentro do prazo desejado"
                : "Ver condições do cenário"}
        </span>
      )}
      {cortes.length > 0 && (
          <div className="spec"><details>
            <summary className="small" style={{ fontWeight: 800, cursor: "pointer" }}>
              {cortes.length} categorias com corte
            </summary>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18, display: "flex", flexDirection: "column", gap: 2 }}>
              {cortes.map((c, i) => (
                <li key={`${txt(c, "micro")}-${i}`} className="small num" style={{ fontWeight: 700 }}>
                  {txt(c, "micro") ?? txt(c, "macro")}: {brl(num(c, "valor_mensal"))}/mês
                </li>
              ))}
            </ul>
          </details></div>
      )}
      {tradeOffs.length > 0 && (
        <details className="cenario-observacoes">
          <summary>O que considerar neste caminho</summary>
          <ul>
            {tradeOffs.map((t) => <li key={t}>{t}</li>)}
          </ul>
        </details>
      )}
      <button
        type="button"
        className="btn btn-secondary"
        style={{ marginTop: "auto" }}
        disabled={bloqueado}
        aria-pressed={escolhido || undefined}
        onClick={() => onEscolher(nome)}
      >
        {escolhido ? (
          <>
            <Icone nome="check" tamanho="sm" traco={3} />
            Caminho escolhido
          </>
        ) : (
          `Escolher plano de ${meses(prazo)}`
        )}
      </button>
    </article>
  );
}

interface Props {
  item: ItemCard;
  onEnviar: (texto: string) => void;
  ocupado: boolean;
  /** Cenário já escolhido no state atual (desabilita as escolhas). */
  cenarioEscolhido?: string | null;
}

export function ComparadorCenarios({ item, onEnviar, ocupado, cenarioEscolhido }: Props) {
  const [valor, setValor] = useState("");
  const idCampo = useId();
  const dados = dadosDe(item.resposta);
  const cenarios = lista(dados, "cenarios");
  const recomendado = cenarioRecomendado(cenarios, item.recomendado);
  const prazoObjetivo = num(obj(item.estado as Dados, "objetivo"), "prazo_meses");
  const bloqueado = ocupado || Boolean(cenarioEscolhido);

  const simular = (e: FormEvent) => {
    e.preventDefault();
    const limpo = valor.trim();
    if (!limpo) return;
    onEnviar(`E se eu guardar ${/^r\$/i.test(limpo) ? limpo : `R$ ${limpo}`} por mês?`);
    setValor("");
  };

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 12 }} aria-label="Comparação de caminhos para o objetivo">
      <CabecalhoCard tag="recomendacao" textoTag="Cenários" resposta={item.resposta} />
      <div className="note note-info" style={{ padding: "12px 14px", lineHeight: "21px" }}>
        <Icone nome="info" tamanho="sm" />
        <span>Compare o prazo, o valor mensal e os cortes necessários. O caminho mais rápido pode deixar menos folga no orçamento.</span>
      </div>
      <div role="group" aria-label="Cenários para o seu objetivo" className="grid-cen">
        {cenarios.map((c) => (
          <CardCenario
            key={txt(c, "nome")}
            cenario={c}
            recomendado={txt(c, "nome") === recomendado}
            escolhido={txt(c, "nome") === cenarioEscolhido}
            bloqueado={bloqueado}
            prazoObjetivo={prazoObjetivo}
            onEscolher={(nome) => onEnviar(`Quero o caminho ${nome}`)}
          />
        ))}
      </div>
      {!cenarioEscolhido && (
        <form className="glass-card" onSubmit={simular} style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
          <label htmlFor={idCampo} style={{ fontSize: 15, fontWeight: 800 }}>
            Prefere outro valor mensal? Simule aqui
          </label>
          <div className="field">
            <input
              id={idCampo}
              inputMode="decimal"
              autoComplete="off"
              placeholder="ex.: R$ 2.000"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              disabled={ocupado}
            />
            <button type="submit" className="btn btn-secondary btn-sm" disabled={ocupado || !valor.trim()}>
              Simular
            </button>
          </div>
        </form>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
      <Disclaimer>{DISCLAIMER_SIMULACAO}</Disclaimer>
    </section>
  );
}
