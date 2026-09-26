// Header do desktop (HeaderBussola.dc.html): marca, selo, vistas, tema,
// toggle dos Bastidores e cliente demo.
import { Icone } from "../base/Icone";
import { SeloSintetico } from "../base/SeloSintetico";

interface Props {
  bastidores: boolean;
  onBastidores: () => void;
  escuro: boolean;
  onTema: () => void;
  /** Abre as vistas do plano (P1–P5). */
  onMeuPlano: () => void;
}

export function HeaderBussola({ bastidores, onBastidores, escuro, onTema, onMeuPlano }: Props) {
  return (
    <header
      className="glass-chrome hdr"
      style={{ height: 60, borderRadius: 20, display: "flex", alignItems: "center", gap: 14, padding: "0 12px 0 14px", flexShrink: 0, whiteSpace: "nowrap" }}
    >
      <span className="brand-mark" aria-hidden="true">
        <Icone nome="bussola" />
      </span>
      <span style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 20, fontWeight: 900 }}>Bússola</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-3)" }}>na ia.i</span>
      </span>
      <span style={{ flex: "1 1 auto" }} />
      <SeloSintetico />
      <button type="button" className="toggle" onClick={onMeuPlano}>
        <Icone nome="alvo" />
        Meu plano
      </button>
      <button
        type="button"
        className="icon-btn"
        aria-label={escuro ? "Usar tema claro" : "Usar tema escuro"}
        aria-pressed={escuro}
        onClick={onTema}
        style={{ width: 40, height: 40, borderRadius: 999 }}
      >
        <Icone nome={escuro ? "sol" : "lua"} />
      </button>
      <button type="button" className="toggle" aria-pressed={bastidores} onClick={onBastidores}>
        <span className={bastidores ? "switch on" : "switch"} aria-hidden="true">
          <span className="knob" />
        </span>
        Bastidores
      </button>
      <span className="vsep" aria-hidden="true" />
      <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className="avatar" aria-hidden="true">
          F
        </span>
        <span className="hdr-cliente">
          <span style={{ fontSize: 15, fontWeight: 800 }}>Fernando</span>
          <span style={{ fontSize: 12.5, color: "var(--ink-3)" }}>Cliente demo</span>
        </span>
      </span>
    </header>
  );
}
