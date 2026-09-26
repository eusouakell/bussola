// Plano criado (AGIR): meta, aporte, prazo e próximos passos. Passos com
// `acao` pedem autorização própria; o botão só manda o texto ao agente (FR-013).
import { avisosDe, dadosDe } from "../../agente/envelope";
import type { Consentimento } from "../../agente/tipos";
import { brl, mascararId, meses } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { Icone } from "../base/Icone";
import { capitalizar, lista, num, txt } from "./ler";
import { CabecalhoCard, Kpi } from "./partes";

interface Props {
  item: ItemCard;
  consentimentos: Record<string, Consentimento> | undefined;
  onEnviar: (texto: string) => void;
  ocupado: boolean;
}

export function CardPlano({ item, consentimentos, onEnviar, ocupado }: Props) {
  const dados = dadosDe(item.resposta);
  const passos = lista(dados, "proximos_passos");
  const descricao = item.estado.objetivo?.descricao;
  return (
    <article className="glass-card card-pad enter" aria-label="CardPlano">
      <CabecalhoCard
        tag="acao"
        textoTag="Ação · plano criado"
        direita={
          <span className="mono" style={{ color: "var(--ink-3)" }}>
            plano {mascararId(txt(dados, "plano_id"))}
          </span>
        }
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span className="t-title" style={{ fontSize: 22 }}>
          {descricao || "Seu plano"}
        </span>
        {txt(dados, "cenario") && <span className="small">Caminho {capitalizar(txt(dados, "cenario"))}</span>}
      </div>
      <div className="grid-kpi">
        <Kpi rotulo="Meta" valor={brl(num(dados, "valor_alvo"))} />
        <Kpi rotulo="Aporte" valor={brl(num(dados, "aporte_mensal"))} sufixo="/mês" />
        <Kpi rotulo="Prazo" valor={meses(num(dados, "prazo_meses"))} />
      </div>
      {passos.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span className="eyebrow">Próximos passos</span>
          <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            {passos.map((p, i) => {
              const texto = txt(p, "texto") ?? "";
              const acao = txt(p, "acao");
              const feito = acao ? consentimentos?.[acao]?.status === "aceito" : false;
              if (!acao) {
                return (
                  <li key={texto} className="check-item" style={{ alignItems: "center" }}>
                    <span className="check-box">{i + 1}</span>
                    <span style={{ fontSize: 16, fontWeight: 700 }}>{texto}</span>
                  </li>
                );
              }
              return (
                <li
                  key={texto}
                  className="check-item"
                  style={
                    feito
                      ? { alignItems: "center" }
                      : { alignItems: "center", flexWrap: "wrap", borderColor: "var(--consent-edge)", boxShadow: "0 0 0 4px var(--consent-halo)" }
                  }
                >
                  <span className="check-box" style={feito ? { background: "var(--ok)", borderColor: "var(--ok)", color: "#fff" } : undefined}>
                    {feito ? <Icone nome="check" tamanho="sm" traco={3} /> : i + 1}
                  </span>
                  <span style={{ fontSize: 16, fontWeight: 700, flex: "1 1 auto" }}>{texto}</span>
                  {feito ? (
                    <span className="badge badge-ok">Autorizado</span>
                  ) : (
                    <>
                      <span className="tag tag-acao" style={{ height: 24, fontSize: 12 }}>
                        <Icone nome="escudo" tamanho="sm" />
                        requer autorização
                      </span>
                      <button type="button" className="btn btn-secondary btn-sm" disabled={ocupado} onClick={() => onEnviar(texto)}>
                        Quero fazer isso
                      </button>
                    </>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
    </article>
  );
}
