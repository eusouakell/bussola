// Topo do mobile (MTopo.dc.html): marca, Bastidores e stepper compacto.
import type { EstadoJornada } from "../../agente/tipos";
import { Icone } from "../base/Icone";
import { SeloSintetico } from "../base/SeloSintetico";
import { StepperCompacto } from "../jornada/StepperJornada";

interface Props {
  atual: EstadoJornada | undefined;
  onBastidores: () => void;
  onMeuPlano: () => void;
  escuro: boolean;
  onTema: () => void;
}

export function MTopo({ atual, onBastidores, onMeuPlano, escuro, onTema }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, flexShrink: 0 }}>
      <header
        className="glass-chrome"
        style={{ height: 56, borderRadius: 20, display: "flex", alignItems: "center", gap: 8, padding: "0 6px 0 10px" }}
      >
        <span className="brand-mark sm" aria-hidden="true">
          <Icone nome="bussola" tamanho="sm" />
        </span>
        <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.15, flex: "1 1 auto", minWidth: 0 }}>
          <span style={{ fontSize: 17, fontWeight: 900 }}>Bússola</span>
          <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-3)" }}>assistente financeiro</span>
        </span>
        <button type="button" className="icon-btn" aria-label="Meu plano" onClick={onMeuPlano} style={{ border: 0 }}>
          <Icone nome="alvo" />
        </button>
        <button
          type="button"
          className="icon-btn"
          aria-label={escuro ? "Usar tema claro" : "Usar tema escuro"}
          aria-pressed={escuro}
          onClick={onTema}
          style={{ border: 0 }}
        >
          <Icone nome={escuro ? "sol" : "lua"} />
        </button>
        <button type="button" className="icon-btn" aria-label="Abrir Bastidores" onClick={onBastidores} style={{ border: 0 }}>
          <Icone nome="painel" />
        </button>
      </header>
      <div className="row-between" style={{ flexWrap: "nowrap" }}>
        <StepperCompacto atual={atual} />
        <SeloSintetico compacto />
      </div>
    </div>
  );
}
