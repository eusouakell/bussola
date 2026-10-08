// Simulação do objetivo (ANTECIPAR): aporte exigido (modo prazo) ou prazo
// resultante (modo aporte), premissas explícitas e disclaimer.
import { avisosDe, dadosDe } from "../../agente/envelope";
import { brl, fracaoPercentual, meses } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { DISCLAIMER_SIMULACAO, Disclaimer } from "../base/Disclaimer";
import { Icone } from "../base/Icone";
import { bool, num, obj, txt } from "./ler";
import { CabecalhoCard } from "./partes";

function textoPremissas(p: Record<string, unknown> | undefined): string[] {
  if (!p) return [];
  const saida: string[] = [];
  const rendimento = num(p, "rendimento_mensal");
  if (rendimento !== undefined) {
    saida.push(rendimento === 0 ? "sem rendimento considerado" : `rendimento de ${fracaoPercentual(rendimento)} ao mês`);
  }
  const usarSaldo = bool(p, "usar_saldo_atual");
  if (usarSaldo === false) saida.push("sem usar o saldo atual da conta");
  if (usarSaldo === true) saida.push(`partindo de ${brl(num(p, "saldo_inicial"))} já guardados`);
  if (txt(p, "base_capacidade") === "sobra_mediana") {
    const n = num(p, "meses_considerados");
    saida.push(n !== undefined ? `sobra mediana (valor central de ${meses(n)} de histórico)` : "sobra mediana");
  }
  return saida;
}

export function CardSimulacao({ item }: { item: ItemCard }) {
  const dados = dadosDe(item.resposta);
  const premissas = obj(dados, "premissas");
  const valor = num(dados, "valor_alvo");
  const aporte = num(dados, "aporte_mensal");
  const prazo = num(dados, "prazo_meses");
  const capacidade = num(premissas, "capacidade_mensal");
  const folga = num(dados, "folga_mensal");
  const viavel = bool(dados, "viavel");
  const modoAporte = txt(dados, "modo") === "aporte";
  const largura =
    aporte !== undefined && capacidade ? `${Math.min(100, Math.max(2, (aporte / capacidade) * 100))}%` : "0%";
  const lista = textoPremissas(premissas);

  return (
    <article className="glass-card card-pad enter" aria-label="Simulação do objetivo financeiro">
      <CabecalhoCard tag="simulacao" resposta={item.resposta} />
      <div style={{ display: "flex", alignItems: "flex-end", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: "1 1 auto", minWidth: 0 }}>
          <span className="prose" style={{ fontWeight: 700, color: "var(--ink-2)" }}>
            {modoAporte ? (
              <>
                Guardando <strong className="num">{brl(aporte)}</strong>/mês, você junta <strong className="num">{brl(valor)}</strong> em
              </>
            ) : (
              <>
                Juntar <strong className="num">{brl(valor)}</strong> em <strong className="num">{meses(prazo)}</strong> exige
              </>
            )}
          </span>
          <span className="kpi-xl">
            {modoAporte ? (
              meses(prazo)
            ) : (
              <>
                {brl(aporte)}
                <span style={{ fontSize: 20, fontWeight: 800, color: "var(--ink-2)" }}>/mês</span>
              </>
            )}
          </span>
        </div>
        {viavel !== undefined && (
          <span className={viavel ? "badge badge-ok" : "badge badge-warn"} style={{ height: 34, fontSize: 14 }}>
            <Icone nome={viavel ? "check" : "alerta"} tamanho="sm" traco={viavel ? 3 : undefined} />
            {viavel ? "Dentro da sobra estimada" : "Acima da sobra estimada"}
          </span>
        )}
      </div>

      {capacidade !== undefined && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div className="meter lg" aria-hidden="true">
            <span style={{ width: largura, background: viavel === false ? "var(--warn-fill)" : "var(--tag-sim)" }} />
          </div>
          <div className="row-between">
            <span className="small num">Aporte {brl(aporte)}</span>
            <span className="small num">Sobra típica (mediana) {brl(capacidade)}</span>
          </div>
          {folga !== undefined && (
            <span className="small num" style={{ fontWeight: 700, color: folga < 0 ? "var(--warn)" : "var(--ok)" }}>
              {folga < 0 ? `Faltam ${brl(Math.abs(folga))}/mês na sua sobra` : `Sobram ${brl(folga)}/mês de folga`}
            </span>
          )}
          <span className="small">A sobra é uma estimativa baseada no histórico e pode variar de um mês para outro.</span>
        </div>
      )}

      {lista.length > 0 && (
        <div className="note note-info" style={{ fontSize: 14.5, lineHeight: "20px", padding: "10px 12px" }}>
          <Icone nome="info" />
          <span>
            <strong>Premissas:</strong> {lista.join(" · ")}
          </span>
        </div>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
      <Disclaimer>{DISCLAIMER_SIMULACAO}</Disclaimer>
    </article>
  );
}
