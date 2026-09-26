// Recusa de guardrail (FR-019): E1 (bloqueio) e E2 (promessa de crédito).
import type { ItemGuardrail } from "../../sessao/modelo";
import { DISCLAIMER_SIMULACAO, Disclaimer } from "../base/Disclaimer";
import { Icone } from "../base/Icone";
import { blocosDeTexto } from "./MensagemAgente";
import { RespostasRapidas } from "./RespostasRapidas";

interface Props {
  item: ItemGuardrail;
  /** Respostas rápidas só no bloqueio mais recente. */
  ativo: boolean;
  onEnviar: (texto: string) => void;
  ocupado: boolean;
}

/** O título do card já diz a recusa; o texto do agente não a repete. */
function semAbertura(texto: string, abertura: RegExp): string {
  const resto = texto.replace(abertura, "");
  return resto.charAt(0).toUpperCase() + resto.slice(1);
}

export function AlertaGuardrail({ item, ativo, onEnviar, ocupado }: Props) {
  const opcoes = ativo ? (item.respostasRapidas ?? []) : [];
  if (item.motivo === "promessa_credito") {
    const corpo = semAbertura(item.texto, /^Não consigo garantir aprovação de crédito(?:, porque |\.\s*)/);
    return (
      <article className="glass-card enter card-pad" aria-label="AlertaGuardrail" style={{ gap: 12 }}>
        <div className="note note-info" style={{ fontSize: 14, lineHeight: "19px", padding: "9px 12px" }}>
          <Icone nome="info" />
          Não consigo garantir aprovação de crédito.
        </div>
        {blocosDeTexto(corpo)}
        <RespostasRapidas opcoes={opcoes} onEscolher={onEnviar} desabilitado={ocupado} />
        <Disclaimer>{DISCLAIMER_SIMULACAO}</Disclaimer>
      </article>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <article className="glass-card enter card-pad" role="alert" aria-label="AlertaGuardrail" style={{ gap: 12, borderColor: "var(--line-strong)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            className="shield-badge"
            style={{ width: 40, height: 40, borderRadius: 13, background: "var(--row)", color: "var(--ink-2)", border: "1px solid var(--line)" }}
          >
            <Icone nome="escudo" tamanho="lg" />
          </span>
          <span style={{ fontSize: 16, fontWeight: 900 }}>Não posso fazer isso</span>
        </div>
        {blocosDeTexto(semAbertura(item.texto, /^Não posso fazer isso\.?\s*/))}
        <RespostasRapidas opcoes={opcoes} onEscolher={onEnviar} desabilitado={ocupado} />
      </article>
      <span className="small" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, paddingLeft: 4 }}>
        <Icone nome="lista" tamanho="sm" />
        Registrado em Bastidores: <span className="mono">guardrail_bloqueio</span>
      </span>
    </div>
  );
}
