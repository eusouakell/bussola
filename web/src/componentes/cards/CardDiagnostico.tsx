// Diagnóstico (ENTENDER): perfil_financeiro + capacidade_poupanca do mesmo turno.
// DADOS_INSUFICIENTES de qualquer um vira aviso âmbar aqui dentro (E4).
import { avisosDe, dadosDe, fonteDe } from "../../agente/envelope";
import type { Dados, RespostaFerramenta } from "../../agente/tipos";
import { brl, mesAbrev } from "../../formatacao/formatar";
import { mensagemErro } from "../../sessao/catalogo";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { ChipFonte } from "../base/ChipFonte";
import { Icone } from "../base/Icone";
import { num, obj } from "./ler";
import { CabecalhoCard, Kpi } from "./partes";

function resposta(item: ItemCard, nome: string): RespostaFerramenta | undefined {
  return item.nome === nome ? item.resposta : item.complementos[nome];
}

/** Série mensal de sobra como linha: escala só visual, sem valor novo. */
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
  const faltas = [rPerfil, rCapacidade]
    .map((r, i) => (r?.tipo === "erro" ? mensagemErro(r.codigo, i === 0 ? "perfil_financeiro" : "capacidade_poupanca") : null))
    .filter((m): m is string => m !== null);
  const avisos = [...new Set([...avisosDe(rPerfil), ...avisosDe(rCapacidade)])];
  const periodo = fonteDe(rPerfil)?.periodo ?? fonteDe(rCapacidade)?.periodo;

  return (
    <article className="glass-card card-pad enter" aria-label="CardDiagnostico">
      <CabecalhoCard tag="diagnostico" resposta={perfilOk ? rPerfil : rCapacidade} />
      <span className="t-title">Seu mês, em média</span>

      {perfilOk || capacidadeOk ? (
        <div className="grid-diag">
          {perfilOk && <Kpi rotulo="Renda média" valor={brl(num(perfil, "renda_media"))} />}
          {perfilOk && <Kpi rotulo="Gasto médio" valor={brl(num(perfil, "gasto_medio"))} />}
          <div className="kpi-box" style={{ background: "var(--tag-diag-bg)", gridColumn: perfilOk ? undefined : "1 / -1" }}>
            <span className="kpi-label" style={{ color: "var(--tag-diag)" }}>
              Sobra mediana
            </span>
            <span className="kpi">
              <span className="kpi-valor">{brl(sobraMediana)}</span>
              <span style={{ fontSize: 15, fontWeight: 800, color: "var(--ink-2)" }}>/mês</span>
            </span>
            {sobraMedia !== undefined && <span className="small num">média {brl(sobraMedia)}</span>}
            {perfilOk && <Sparkline serie={serieSobra(perfil)} />}
          </div>
        </div>
      ) : null}

      {(saldo || capacidadeOk) && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          {saldo && (
            <span className="small num" style={{ fontWeight: 700 }}>
              Saldo mín{" "}
              <strong style={{ color: (num(saldo, "minimo") ?? 0) < 0 ? "var(--err)" : "var(--ink)" }}>{brl(num(saldo, "minimo"))}</strong>
              {" · "}máx <strong style={{ color: "var(--ink)" }}>{brl(num(saldo, "maximo"))}</strong>
            </span>
          )}
          {capacidadeOk && num(capacidade, "desvio_padrao") !== undefined && (
            <span className="small num" style={{ fontWeight: 700 }}>
              Oscilação da sobra <strong style={{ color: "var(--ink)" }}>{brl(num(capacidade, "desvio_padrao"))}</strong>
            </span>
          )}
          <span style={{ flex: "1 1 auto" }} />
          {perfilOk && capacidadeOk && <ChipFonte fonte={fonteDe(rCapacidade)} avisos={avisosDe(rCapacidade)} />}
        </div>
      )}

      {faltas.map((m) => (
        <div key={m} className="note note-warn" role="note" style={{ fontSize: 14.5, lineHeight: "20px", padding: "10px 12px" }}>
          <Icone nome="alerta" />
          <span>{m}</span>
        </div>
      ))}
      <Avisos avisos={avisos} />
      {periodo && (
        <span className="sr-only">
          Período analisado: {mesAbrev(periodo.inicio)} a {mesAbrev(periodo.fim)}
        </span>
      )}
    </article>
  );
}
