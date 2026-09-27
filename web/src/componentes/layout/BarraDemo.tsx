// Barra do apresentador (FR-014, FR-015, FR-021, FR-023): mês de referência,
// "Avançar um mês", modo de execução e cenários de borda do simulado.
import { useId } from "react";
import type { Bordas, Modo } from "../../agente/transporte";
import type { EstadoSessao } from "../../agente/tipos";
import { CONFIG } from "../../config";
import { mesAbrev } from "../../formatacao/formatar";
import { motivoSemAvanco } from "../../sessao/avanco";
import { R_AVANCAR, TEXTO_AVANCAR } from "../../sessao/sugestoes-padrao";
import { Icone } from "../base/Icone";

const BORDAS: { chave: keyof Bordas; rotulo: string; descricao: string }[] = [
  { chave: "e3", rotulo: "E3 · Ferramenta com erro", descricao: "oportunidades de corte falham uma vez" },
  { chave: "e4", rotulo: "E4 · Dados insuficientes", descricao: "capacidade de poupança sem histórico" },
  { chave: "e5", rotulo: "E5 · Resposta lenta", descricao: "skeleton e cursor de digitação" },
];

interface Props {
  estado: EstadoSessao;
  modo: Modo;
  onModo: (modo: Modo) => void;
  onEnviar: (texto: string) => void;
  ocupado: boolean;
  bordas: Bordas;
  onBordas: (bordas: Partial<Bordas>) => void;
  /** Persona logada no BFF (modo ao vivo com login). */
  persona?: { nome: string; onTrocar: () => void };
}

export function BarraDemo({ estado, modo, onModo, onEnviar, ocupado, bordas, onBordas, persona }: Props) {
  const idMotivo = useId();
  const idModo = useId();
  const motivo = motivoSemAvanco(estado);
  const ativas = BORDAS.filter((b) => bordas[b.chave]).length;
  return (
    <section className="presenter" aria-label="Modo demonstração" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <span className="pe">Modo demonstração</span>
          <span style={{ fontSize: 14, fontWeight: 800 }} className="num">
            Mês de referência: {mesAbrev(estado.ate_anomes ?? CONFIG.anomesInicial)}
          </span>
        </div>
        <button
          type="button"
          className="btn-presenter"
          disabled={Boolean(motivo) || ocupado}
          aria-describedby={motivo ? idMotivo : undefined}
          onClick={() => onEnviar(TEXTO_AVANCAR)}
        >
          {R_AVANCAR}
          <Icone nome="avancar" tamanho="sm" />
        </button>
      </div>
      {motivo && (
        <span id={idMotivo} style={{ fontSize: 12.5, fontWeight: 700, color: "rgba(244, 246, 249, 0.78)" }}>
          {motivo}
        </span>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <label htmlFor={idModo} className="pe">
          Agente
        </label>
        <select id={idModo} value={modo} onChange={(e) => onModo(e.target.value === "ao-vivo" ? "ao-vivo" : "simulado")}>
          <option value="simulado">Simulado</option>
          <option value="ao-vivo">Ao vivo (ADK)</option>
        </select>
        {modo === "ao-vivo" && persona && (
          <>
            <span style={{ fontSize: 13.5, fontWeight: 800 }}>Persona: {persona.nome}</span>
            <button type="button" className="btn-presenter" style={{ minHeight: 36 }} disabled={ocupado} onClick={persona.onTrocar}>
              Trocar persona
            </button>
          </>
        )}
        {modo === "simulado" && (
          <details style={{ position: "relative" }}>
            <summary className="btn-presenter" style={{ minHeight: 36, listStyle: "none" }}>
              Cenários de borda{ativas > 0 ? ` · ${ativas}` : ""}
              <Icone nome="chevronBaixo" tamanho="sm" />
            </summary>
            <fieldset
              style={{
                margin: "8px 0 0",
                padding: 10,
                border: "1px solid rgba(255, 255, 255, 0.3)",
                borderRadius: 12,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <legend className="sr-only">Cenários de borda</legend>
              {BORDAS.map((b) => (
                <label key={b.chave} style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 13.5, fontWeight: 700, minHeight: 32 }}>
                  <input
                    type="checkbox"
                    checked={bordas[b.chave]}
                    onChange={(e) => onBordas({ [b.chave]: e.target.checked })}
                    style={{ width: 18, height: 18, marginTop: 1, accentColor: "var(--accent)" }}
                  />
                  <span style={{ display: "flex", flexDirection: "column" }}>
                    {b.rotulo}
                    <span style={{ fontSize: 12, fontWeight: 600, color: "rgba(244, 246, 249, 0.72)" }}>{b.descricao}</span>
                  </span>
                </label>
              ))}
            </fieldset>
          </details>
        )}
      </div>
    </section>
  );
}
