// Planos financeiros: uma alternativa por vez; linguagem simples na interface.
// Mantém nomes e dados do agente no envio, sem recalcular recomendações.
import { useId, useState, type FormEvent } from "react";
import { avisosDe, dadosDe } from "../../agente/envelope";
import type { Dados } from "../../agente/tipos";
import { brl, fracaoPercentual, meses } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { DISCLAIMER_SIMULACAO, Disclaimer } from "../base/Disclaimer";
import { bool, capitalizar, lista, num, obj, textos, txt } from "./ler";

/** Metadado do agente ou, quando ausente, plano viável com menor uso da sobra. */
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

/** Tradução de um detalhe produzido pelo agente. Só a apresentação é alterada. */
export function explicarConsequencia(texto: string): string {
  return texto
    .replace(/Compromete (\d+)% da sobra mensal mediana[^.]*(\.)?/i, (_, pct: string) =>
      `Para seguir este plano, você usaria ${pct}% do dinheiro que costuma sobrar no mês.`)
    .replace(/sobra mensal mediana/gi, "dinheiro que costuma sobrar no mês")
    .replace(/aporte mensal/gi, "valor guardado por mês");
}

export function CardCenario({ cenario, recomendado, escolhido, bloqueado, prazoObjetivo, onEscolher }: CenarioProps) {
  const nome = txt(cenario, "nome") ?? "cenário";
  const pct = num(cenario, "pct_capacidade");
  const viavel = bool(cenario, "viavel");
  const prazo = num(cenario, "prazo_meses");
  const aporte = num(cenario, "aporte_mensal");
  const cortes = lista(cenario, "cortes_sugeridos");
  const economiaAdicional = cortes.reduce((total, corte) => total + (num(corte, "valor_mensal") ?? 0), 0);
  const aporteBase = aporte !== undefined ? aporte - economiaAdicional : undefined;
  const sobraBase = pct !== undefined && pct > 0 && aporteBase !== undefined ? aporteBase / pct : undefined;
  const proporcaoTotal = sobraBase && aporte !== undefined ? aporte / sobraBase : undefined;
  const noPrazo = prazoObjetivo !== undefined && prazo !== undefined ? prazo <= prazoObjetivo : undefined;
  const atraso = prazoObjetivo !== undefined && prazo !== undefined && prazo > prazoObjetivo
    ? prazo - prazoObjetivo : undefined;
  const tradeOffs = textos(cenario, "trade_offs")
    .filter((texto) => economiaAdicional === 0 || !/^Compromete \d+% da sobra/i.test(texto))
    .map(explicarConsequencia);

  return (
    <article className="glass-card cen cen-simples" aria-label={`Cenário ${capitalizar(nome)}${recomendado ? ", em destaque" : ""}`}>
      <header className="cenario-cabecalho">
        <div>
          <h3 className="t-title">{prazo !== undefined ? `Plano de ${meses(prazo)}` : "Outra opção de plano"}</h3>
          <span className="small">Prazo estimado</span>
        </div>
        {recomendado && <span className="cenario-selo">Em destaque</span>}
      </header>

      <div className="cenario-valor">
        <span className="small">Guardar por mês</span>
        <strong className="kpi num">{brl(aporte)}</strong>
      </div>

      {atraso !== undefined && (
        <p className="cenario-alerta" role="note">{meses(atraso)} depois do prazo que você escolheu.</p>
      )}
      {viavel === false && (
        <p className="cenario-alerta" role="note">Esse valor é maior que o dinheiro que costuma sobrar no mês.</p>
      )}
      {noPrazo === true && viavel !== false && (
        <p className="cenario-estado">Dentro do prazo que você escolheu.</p>
      )}
      {economiaAdicional > 0 && (
        <p className="cenario-alerta" role="note">
          Para isso, seria preciso reduzir gastos em {brl(economiaAdicional)} por mês.
        </p>
      )}

      {(pct !== undefined || cortes.length > 0 || tradeOffs.length > 0) && (
        <details className="cenario-detalhes">
          <summary>Entenda os valores deste plano</summary>
          <div className="cenario-detalhes-corpo">
            {proporcaoTotal !== undefined && (
              <p>Você usaria cerca de <strong>{fracaoPercentual(proporcaoTotal)}</strong> do dinheiro que costuma sobrar no mês.</p>
            )}
            {proporcaoTotal === undefined && pct !== undefined && (
              <p>Você usaria cerca de <strong>{fracaoPercentual(pct)}</strong> do dinheiro que costuma sobrar no mês.</p>
            )}
            {economiaAdicional > 0 && aporteBase !== undefined && (
              <p>{brl(aporteBase)} do dinheiro que já costuma sobrar + {brl(economiaAdicional)} em economias que ainda precisariam acontecer.</p>
            )}
            {cortes.length > 0 && (
              <>
                <strong>Onde seria preciso economizar</strong>
                <ul>{cortes.map((c, i) => (
                  <li key={`${txt(c, "micro")}-${i}`}>
                    {txt(c, "micro") ?? txt(c, "macro")}: {brl(num(c, "valor_mensal"))}/mês
                  </li>
                ))}</ul>
              </>
            )}
            {tradeOffs.length > 0 && (
              <>
                <strong>O que mais considerar</strong>
                <ul>{tradeOffs.map((t) => <li key={t}>{t}</li>)}</ul>
              </>
            )}
            <p>Os valores são estimativas com base nos meses analisados. A quantia disponível pode mudar.</p>
          </div>
        </details>
      )}

      <button
        type="button"
        className="btn btn-secondary cenario-escolher"
        disabled={bloqueado}
        aria-pressed={escolhido || undefined}
        aria-label={escolhido ? "Plano escolhido" : `Escolher plano de ${meses(prazo)}`}
        onClick={() => onEscolher(nome)}
      >
        {escolhido ? "Plano escolhido" : "Escolher este plano"}
      </button>
    </article>
  );
}

interface Props {
  item: ItemCard;
  onEnviar: (texto: string) => void;
  ocupado: boolean;
  cenarioEscolhido?: string | null;
}

export function ComparadorCenarios({ item, onEnviar, ocupado, cenarioEscolhido }: Props) {
  const [valor, setValor] = useState("");
  const [opcao, setOpcao] = useState<string | null>(null);
  const idCampo = useId();
  const dados = dadosDe(item.resposta);
  const cenarios = lista(dados, "cenarios");
  const recomendado = cenarioRecomendado(cenarios, item.recomendado);
  const prazoObjetivo = num(obj(item.estado as Dados, "objetivo"), "prazo_meses");
  const bloqueado = ocupado || Boolean(cenarioEscolhido);
  const escolhidaParaVer = cenarioEscolhido ?? opcao ?? recomendado ?? txt(cenarios[0], "nome");
  const atual = cenarios.find((c) => txt(c, "nome") === escolhidaParaVer) ?? cenarios[0];

  const simular = (e: FormEvent) => {
    e.preventDefault();
    const limpo = valor.trim();
    if (!limpo) return;
    onEnviar(`E se eu guardar ${/^r\$/i.test(limpo) ? limpo : `R$ ${limpo}`} por mês?`);
    setValor("");
  };

  return (
    <section className="comparador-simples" aria-label="Planos para seu objetivo">
      <div className="comparador-intro">
        <h2>Compare os planos</h2>
        <p>Escolha um prazo para ver quanto precisaria guardar por mês.</p>
      </div>
      <div role="group" aria-label="Escolha um prazo para comparar" className="cenario-opcoes">
        {cenarios.map((c) => {
          const nome = txt(c, "nome") ?? "cenário";
          const selecionado = nome === txt(atual, "nome");
          return (
            <button
              key={nome}
              type="button"
              className={selecionado ? "cenario-opcao ativa" : "cenario-opcao"}
              aria-pressed={selecionado}
              onClick={() => setOpcao(nome)}
            >
              <span>{meses(num(c, "prazo_meses"))}</span>
              <small>{brl(num(c, "aporte_mensal"))}/mês</small>
            </button>
          );
        })}
      </div>
      {atual && (
        <div className="cenario-unico">
          <CardCenario
            key={txt(atual, "nome")}
            cenario={atual}
            recomendado={txt(atual, "nome") === recomendado}
            escolhido={txt(atual, "nome") === cenarioEscolhido}
            bloqueado={bloqueado}
            prazoObjetivo={prazoObjetivo}
            onEscolher={(nome) => onEnviar(`Quero o caminho ${nome}`)}
          />
        </div>
      )}
      {!cenarioEscolhido && (
        <details className="cenario-outro">
          <summary>Quero guardar outro valor</summary>
          <form onSubmit={simular} className="cenario-outro-form">
            <label htmlFor={idCampo}>Quanto você quer guardar por mês?</label>
            <div className="field">
              <input id={idCampo} inputMode="decimal" autoComplete="off" placeholder="Ex.: R$ 500"
                value={valor} onChange={(e) => setValor(e.target.value)} disabled={ocupado} />
              <button type="submit" className="btn btn-secondary btn-sm" disabled={ocupado || !valor.trim()}>
                Calcular
              </button>
            </div>
          </form>
        </details>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
      <Disclaimer>{DISCLAIMER_SIMULACAO}</Disclaimer>
    </section>
  );
}
