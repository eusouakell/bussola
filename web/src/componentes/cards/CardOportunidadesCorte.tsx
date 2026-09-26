// Oportunidades de corte (ENTENDER): categorias discricionárias com a economia
// potencial que a ferramenta calculou. Sem totais somados no front (FR-007).
import { useState } from "react";
import { avisosDe, dadosDe } from "../../agente/envelope";
import { brl } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { lista, num, txt } from "./ler";
import { CabecalhoCard } from "./partes";

const VISIVEIS = 5;

export function CardOportunidadesCorte({ item }: { item: ItemCard }) {
  const [todas, setTodas] = useState(false);
  const categorias = lista(dadosDe(item.resposta), "categorias");
  const mostradas = todas ? categorias : categorias.slice(0, VISIVEIS);
  return (
    <article className="glass-card card-pad enter" aria-label="CardOportunidadesCorte">
      <CabecalhoCard tag="diagnostico" resposta={item.resposta} />
      <span className="t-title">Onde dá para economizar</span>
      {categorias.length === 0 ? (
        <p className="small" style={{ margin: 0 }}>
          Não encontrei gastos discricionários com espaço para corte neste período.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          {mostradas.map((c, i) => {
            const micro = txt(c, "micro");
            const macro = txt(c, "macro");
            return (
              <li key={`${macro}-${micro}-${i}`} className="linha-lista">
                <span className="nome">
                  <span>{micro ?? macro ?? "Categoria"}</span>
                  <span className="small">
                    {macro && macro !== micro ? `${macro} · ` : ""}
                    <span className="num">média {brl(num(c, "media_mensal"))}/mês</span>
                  </span>
                  {txt(c, "criterio") && (
                    <span className="small" style={{ fontSize: 13, color: "var(--ink-3)" }}>
                      {txt(c, "criterio")}
                    </span>
                  )}
                </span>
                <span className="valor" style={{ color: "var(--ok)" }}>
                  <span className="small" style={{ display: "block", fontWeight: 700, color: "var(--ink-3)" }}>
                    até
                  </span>
                  {brl(num(c, "economia_potencial_mensal"))}/mês
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {!todas && categorias.length > VISIVEIS && (
        <button type="button" className="link-btn" style={{ alignSelf: "flex-start" }} onClick={() => setTodas(true)}>
          Ver todas as {categorias.length} categorias
        </button>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
    </article>
  );
}
