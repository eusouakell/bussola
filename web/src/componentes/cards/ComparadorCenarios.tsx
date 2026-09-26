// Comparação de cenários (ORIENTAR): três caminhos lado a lado, selo
// Recomendado (metadado do agente ou regra R9) e campo "Outro caminho".
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
  const tradeOffs = textos(cenario, "trade_offs");
  const classes = ["glass-card", "cen", "enter", recomendado ? "rec" : ""].filter(Boolean).join(" ");
  return (
    <article className={classes} aria-label={`Cenário ${capitalizar(nome)}${recomendado ? ", recomendado" : ""}`}>
      {recomendado && (
        <span className="rec-flag">
          <Icone nome="estrela" tamanho="sm" />
          Recomendado
        </span>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span className="t-title">{capitalizar(nome)}</span>
        <span className="small num">{fracaoPercentual(pct)} da sobra</span>
      </div>
      <div className={recomendado ? "meter accent" : "meter"} aria-hidden="true">
        <span style={{ width: pct !== undefined ? `${Math.min(100, pct * 100)}%` : "0%" }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span className="kpi num">
          {brl(num(cenario, "aporte_mensal"))}
          <span style={{ fontSize: 15, fontWeight: 800, color: "var(--ink-2)" }}>/mês</span>
        </span>
        <span className="small num">{meses(prazo)} até a meta</span>
      </div>
      {viavel !== undefined && (
        <span className={viavel ? "badge badge-ok" : "badge badge-warn"} style={{ alignSelf: "flex-start" }}>
          <Icone nome={viavel ? "check" : "alerta"} tamanho="sm" traco={viavel ? 3 : undefined} />
          {prazoObjetivo !== undefined
            ? `${viavel ? "Cabe" : "Não cabe"} em ${meses(prazoObjetivo)}`
            : viavel
              ? "Cabe no prazo"
              : "Não cabe no prazo"}
        </span>
      )}
      <div className="spec">
        <span className="k">Cortes</span>
        {cortes.length === 0 ? (
          <span className="v">—</span>
        ) : (
          <details>
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
          </details>
        )}
      </div>
      {tradeOffs.map((t) => (
        <p key={t} className="quote">
          {t}
        </p>
      ))}
      <button
        type="button"
        className={recomendado ? "btn btn-primary" : "btn btn-secondary"}
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
          "Escolher este caminho"
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
    <section style={{ display: "flex", flexDirection: "column", gap: 12 }} aria-label="ComparadorCenarios">
      <CabecalhoCard tag="recomendacao" textoTag="Cenários" resposta={item.resposta} />
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
            Outro caminho: quanto você quer guardar por mês?
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
