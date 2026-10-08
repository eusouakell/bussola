// Pedido de autorização (FR-011): o que faz, o que não faz, dados usados.
// Autorizar envia "sim"; Agora não envia "não". Decidido, vira recibo.
import { useState } from "react";
import type { Consentimento, Dados } from "../../agente/tipos";
import { dataHora, mascararId } from "../../formatacao/formatar";
import type { ItemConsentimento } from "../../sessao/modelo";
import { Disclaimer } from "../base/Disclaimer";
import { Icone, type NomeIcone } from "../base/Icone";
import { Tag } from "../base/Tag";
import { txt } from "./ler";

type Situacao = "pendente" | "aceito" | "recusado" | "encerrado";

/** Status pelo `session.state`; outro `consent_id` na mesma ação = pedido substituído. */
export function situacaoConsentimento(item: ItemConsentimento, atual: Consentimento | undefined): Situacao {
  if (!atual) return "pendente";
  if (atual.consent_id !== item.consentId) return "encerrado";
  return atual.status;
}

interface Coluna {
  titulo: string;
  icone: NomeIcone;
  cor: string;
  texto: string | undefined;
}

function Colunas({ pedido }: { pedido: Dados | undefined }) {
  const colunas: Coluna[] = [
    { titulo: "O que vou fazer", icone: "check", cor: "var(--ok)", texto: txt(pedido, "o_que_faz") },
    { titulo: "O que não vou fazer", icone: "x", cor: "var(--err)", texto: txt(pedido, "o_que_nao_faz") },
    { titulo: "Dados usados", icone: "db", cor: "var(--ink-2)", texto: txt(pedido, "dados_usados") },
  ];
  return (
    <div className="grid-kpi">
      {colunas.map((c) => (
        <div key={c.titulo} className="c-col">
          <span className="h" style={{ color: c.cor }}>
            <Icone nome={c.icone} tamanho="sm" traco={c.icone === "db" ? undefined : 3} />
            {c.titulo}
          </span>
          <p>{c.texto ?? "—"}</p>
        </div>
      ))}
    </div>
  );
}

interface Props {
  item: ItemConsentimento;
  /** Entrada atual de `estado.consentimentos[acao]`. */
  consentimento: Consentimento | undefined;
  onEnviar: (texto: string) => void;
  ocupado: boolean;
}

export function CardConsentimento({ item, consentimento, onEnviar, ocupado }: Props) {
  const [detalhes, setDetalhes] = useState(false);
  const situacao = situacaoConsentimento(item, consentimento);
  const resumo = txt(item.pedido, "resumo") ?? consentimento?.resumo ?? "Autorizar esta ação";
  const acoes: Record<string, string> = {
    criar_plano: "Autorizar criação do plano",
    ativar_lembretes: "Autorizar lembretes mensais",
    ajustar_plano: "Autorizar ajuste do plano",
    simular_contratacao: "Autorizar simulação de financiamento",
    compartilhar_dados: "Autorizar compartilhamento de dados",
  };
  const rotuloAutorizacao = acoes[item.acao] ?? "Autorizar esta ação";

  if (situacao !== "pendente") {
    const aceito = situacao === "aceito";
    const rotulo = aceito ? "Autorizado" : situacao === "recusado" ? "Não autorizado" : "Pedido encerrado";
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div className={aceito ? "receipt ok enter" : "receipt no enter"} role="status" aria-label="Recibo de consentimento">
          <span className="st" style={{ background: aceito ? "var(--ok)" : "var(--line-strong)", color: "#fff" }}>
            <Icone nome={aceito ? "check" : "x"} tamanho="sm" traco={3} />
          </span>
          <span>
            {rotulo}
            {situacao !== "encerrado" && consentimento?.ts !== undefined && (
              <span className="num" style={{ fontWeight: 700 }}>
                {" "}
                · {dataHora(consentimento.ts)} ·
              </span>
            )}{" "}
            <span className="mono" style={{ fontWeight: 600 }}>
              consentimento {mascararId(item.consentId)}
            </span>
          </span>
          <span style={{ flex: "1 1 auto" }} />
          <button
            type="button"
            className="link-btn"
            aria-expanded={detalhes}
            style={{ color: aceito ? "var(--ok)" : "var(--ink-2)", fontSize: 14 }}
            onClick={() => setDetalhes((d) => !d)}
          >
            {detalhes ? "Esconder detalhes" : "Ver detalhes"}
          </button>
        </div>
        {detalhes && (
          <div className="glass-card card-pad" style={{ gap: 12 }}>
            <span style={{ fontSize: 16, fontWeight: 800 }}>{resumo}</span>
            <Colunas pedido={item.pedido} />
          </div>
        )}
      </div>
    );
  }

  return (
    <article className="glass-consent enter" aria-label={`Pedido de autorização: ${resumo}`} style={{ padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <span className="shield-badge">
          <Icone nome="escudo" tamanho="lg" />
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
          <span style={{ alignSelf: "flex-start" }}>
            <Tag tipo="acao" texto="Ação · requer sua autorização" />
          </span>
          <h2 style={{ margin: 0, fontSize: 24, lineHeight: "30px", fontWeight: 900, letterSpacing: "-0.01em" }}>{resumo}</h2>
        </div>
      </div>
      <Colunas pedido={item.pedido} />
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-auth" disabled={ocupado} onClick={() => onEnviar("sim")}>
          <Icone nome="check" traco={3} />
          {rotuloAutorizacao}
        </button>
        <button type="button" className="btn btn-secondary" disabled={ocupado} onClick={() => onEnviar("não")}>
          Agora não
        </button>
      </div>
      <div className="hline" />
      <Disclaimer icone="escudo">Esta decisão fica registrada e vale somente para a finalidade descrita acima.</Disclaimer>
    </article>
  );
}
