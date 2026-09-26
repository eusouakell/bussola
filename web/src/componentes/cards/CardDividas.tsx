// Dívidas e parcelas (ENTENDER): linha compacta com a lista de parcelas sob demanda.
import { useState } from "react";
import { avisosDe, dadosDe, fonteDe } from "../../agente/envelope";
import { brl, percentual } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { ChipFonte } from "../base/ChipFonte";
import { Icone } from "../base/Icone";
import { Tag } from "../base/Tag";
import { capitalizar, lista, num, txt } from "./ler";

const VISIVEIS = 3;

export function CardDividas({ item }: { item: ItemCard }) {
  const [aberto, setAberto] = useState(false);
  const [todas, setTodas] = useState(false);
  const dados = dadosDe(item.resposta);
  const parcelas = lista(dados, "parcelas_ativas");
  const mostradas = todas ? parcelas : parcelas.slice(0, VISIVEIS);
  const juros = num(dados, "juros_pagos_media");
  return (
    <article className="glass-card enter" aria-label="CardDividas" style={{ padding: "14px 18px", display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Tag tipo="diagnostico" />
        <span style={{ fontSize: 16, fontWeight: 800 }}>
          Parcelas comprometem <span className="num">{percentual(num(dados, "comprometimento_renda_pct"))}</span> da renda
        </span>
        {juros !== undefined && <span className="small num">· juros pagos {brl(juros)}/mês</span>}
        <span style={{ flex: "1 1 auto" }} />
        <ChipFonte fonte={fonteDe(item.resposta)} avisos={avisosDe(item.resposta)} />
      </div>
      {parcelas.length > 0 && (
        <button type="button" className="link-btn" aria-expanded={aberto} onClick={() => setAberto((a) => !a)} style={{ alignSelf: "flex-start" }}>
          {aberto ? "Esconder parcelas" : `Ver parcelas ativas (${parcelas.length})`}
          <Icone nome="chevronBaixo" tamanho="sm" estilo={{ transform: aberto ? "rotate(180deg)" : undefined }} />
        </button>
      )}
      {aberto && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }} aria-label="Parcelas ativas">
          {mostradas.map((p, i) => (
            <li key={`${txt(p, "descr") ?? "parcela"}-${i}`} className="linha-lista">
              <span className="nome">
                <span>{capitalizar(txt(p, "descr"))}</span>
                <span className="small num">
                  parcela {num(p, "parcela_atual") ?? "—"} de {num(p, "parcela_total") ?? "—"} · faltam {num(p, "meses_restantes") ?? "—"}
                </span>
              </span>
              <span className="valor">{brl(num(p, "valor"))}</span>
            </li>
          ))}
          {!todas && parcelas.length > VISIVEIS && (
            <li>
              <button type="button" className="link-btn" onClick={() => setTodas(true)}>
                Ver todas
              </button>
            </li>
          )}
        </ul>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
    </article>
  );
}
