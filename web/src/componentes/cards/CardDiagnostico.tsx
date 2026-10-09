// Resumo do orçamento (ENTENDER): valor útil primeiro, estatísticas sob demanda.
// A mediana continua sendo calculada pela ferramenta, não pela interface.
import { avisosDe, dadosDe, fonteDe } from "../../agente/envelope";
import type { Dados, RespostaFerramenta } from "../../agente/tipos";
import { brl, mesAbrev } from "../../formatacao/formatar";
import { mensagemErro } from "../../sessao/catalogo";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { ChipFonte } from "../base/ChipFonte";
import { Icone } from "../base/Icone";
import { num, obj } from "./ler";
import { Kpi } from "./partes";

function resposta(item: ItemCard, nome: string): RespostaFerramenta | undefined {
  return item.nome === nome ? item.resposta : item.complementos[nome];
}

function Sparkline({ serie }: { serie: number[] }) {
  if (serie.length < 2) return null;
  const min = Math.min(...serie);
  const max = Math.max(...serie);
  const faixa = max - min || 1;
  const pontos = serie.map((v, i) => `${(i / (serie.length - 1)) * 100},${28 - ((v - min) / faixa) * 24}`).join(" ");
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true" style={{ width: "100%", height: 30, marginTop: 6 }}>
      <polyline points={pontos} fill="none" stroke="var(--tag-diag)" strokeWidth={2.2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}
function serieSobra(perfil: Dados): number[] {
  const serie = perfil.serie_mensal;
  if (!Array.isArray(serie)) return [];
  return serie.map((m) => (m as Dados).sobra).filter((v): v is number => typeof v === "number");
}

export function CardDiagnostico({ item }: { item: ItemCard }) {
  const rPerfil = resposta(item, "perfil_financeiro");
  const rCapacidade = resposta(item, "capacidade_poupanca");
  const perfilOk = rPerfil?.tipo === "envelope";
  const capacidadeOk = rCapacidade?.tipo === "envelope";
  const perfil = dadosDe(rPerfil);
  const capacidade = dadosDe(rCapacidade);
  const saldo = obj(perfil, "saldo");
  const sobraMediana = num(capacidade, "sobra_mediana") ?? num(perfil, "sobra_mediana");
  const sobraMedia = num(capacidade, "sobra_media") ?? num(perfil, "sobra_media");
  const faltas = [...new Set([rPerfil, rCapacidade]
    .map((r, i) => r?.tipo === "erro" ? mensagemErro(r.codigo, i === 0 ? "perfil_financeiro" : "capacidade_poupanca") : null)
    .filter((m): m is string => m !== null))];
  const avisos = [...new Set([...avisosDe(rPerfil), ...avisosDe(rCapacidade)])];
  const periodo = fonteDe(rPerfil)?.periodo ?? fonteDe(rCapacidade)?.periodo;

  return (
    <article className="glass-card card-pad enter resumo-orcamento" aria-label="Resumo do orçamento">
      <h3 className="t-title">Quanto costuma sobrar no mês</h3>
      {(perfilOk || capacidadeOk) && (
        <>
          <strong className="resumo-orcamento-valor num">{brl(sobraMediana)}</strong>
          <p className="small">É uma estimativa do histórico. O valor pode mudar a cada mês.</p>
          <details className="cenario-detalhes">
            <summary>Como calculamos esse valor?</summary>
            <div className="cenario-detalhes-corpo">
              <p>Usamos o valor central dos meses analisados: metade dos meses teve uma sobra maior, e metade, menor.</p>
              <div className="grid-diag">
                {perfilOk && <Kpi rotulo="Dinheiro recebido por mês, em média" valor={brl(num(perfil, "renda_media"))} />}
                {perfilOk && <Kpi rotulo="Gastos por mês, em média" valor={brl(num(perfil, "gasto_medio"))} />}
                {sobraMedia !== undefined && <Kpi rotulo="Sobra mensal, em média" valor={brl(sobraMedia)} />}
              </div>
              {saldo && (
                <p className="small num">
                  Menor saldo: <strong>{brl(num(saldo, "minimo"))}</strong> · Maior saldo: <strong>{brl(num(saldo, "maximo"))}</strong>
                </p>
              )}
              {capacidadeOk && num(capacidade, "desvio_padrao") !== undefined && (
                <p className="small num">Variação estimada entre os meses: {brl(num(capacidade, "desvio_padrao"))}</p>
              )}
              {perfilOk && <Sparkline serie={serieSobra(perfil)} />}
              {perfilOk && <ChipFonte fonte={fonteDe(rPerfil)} avisos={avisosDe(rPerfil)} />}
              {capacidadeOk && <ChipFonte fonte={fonteDe(rCapacidade)} avisos={avisosDe(rCapacidade)} />}
            </div>
          </details>
        </>
      )}
      {faltas.map((m) => (
        <div key={m} className="note note-warn" role="note" style={{ fontSize: 14.5, lineHeight: "20px", padding: "10px 12px" }}>
          <Icone nome="alerta" />
          <span>{m}</span>
        </div>
      ))}
      <Avisos avisos={avisos} />
      {periodo && (
        <span className="sr-only">Período analisado: {mesAbrev(periodo.inicio)} a {mesAbrev(periodo.fim)}</span>
      )}
    </article>
  );
}
