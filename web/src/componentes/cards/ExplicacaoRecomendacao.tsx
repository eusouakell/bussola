// Explicação da recomendação (ORIENTAR): trechos da base de conhecimento
// (buscar_contexto_financeiro) atrás de "Por que essa recomendação?".
import { useId, useState } from "react";
import { avisosDe, dadosDe } from "../../agente/envelope";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { Icone } from "../base/Icone";
import { lista, obj, txt } from "./ler";
import { CabecalhoCard } from "./partes";

export function ExplicacaoRecomendacao({ item }: { item: ItemCard }) {
  const [aberto, setAberto] = useState(false);
  const id = useId();
  const trechos = lista(dadosDe(item.resposta), "trechos");
  return (
    <article className="glass-card card-pad enter" aria-label="ExplicacaoRecomendacao" style={{ gap: 12 }}>
      <CabecalhoCard tag="recomendacao" resposta={item.resposta} />
      <p className="prose" style={{ fontSize: 16 }}>
        A recomendação segue boas práticas de planejamento e normas públicas sobre crédito.
      </p>
      {trechos.length > 0 && (
        <button
          type="button"
          className="link-btn"
          aria-expanded={aberto}
          aria-controls={id}
          style={{ alignSelf: "flex-start" }}
          onClick={() => setAberto((a) => !a)}
        >
          Por que essa recomendação?
          <Icone nome="chevronBaixo" tamanho="sm" estilo={{ transform: aberto ? "rotate(180deg)" : undefined }} />
        </button>
      )}
      {aberto && (
        <ul id={id} style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
          {trechos.map((t, i) => {
            const fonte = obj(t, "fonte");
            return (
              <li key={txt(t, "trecho_id") ?? i} className="check-item" style={{ flexDirection: "column", gap: 6 }}>
                <span style={{ fontSize: 15.5, fontWeight: 800 }}>{txt(t, "titulo") ?? "Trecho"}</span>
                <span className="small" style={{ color: "var(--ink-2)" }}>
                  {txt(t, "texto")}
                </span>
                {fonte && (
                  <span className="small" style={{ fontSize: 13, color: "var(--ink-3)", fontWeight: 700 }}>
                    {[txt(fonte, "nome"), txt(fonte, "referencia")].filter(Boolean).join(" · ")}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
    </article>
  );
}
