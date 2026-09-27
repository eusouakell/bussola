// Boas-vindas (Main.dc.html / M1BoasVindas.dc.html): saudação e 4 objetivos.
import { SUGESTOES_INICIAIS } from "../../simulado/textos";
import { Icone, type NomeIcone } from "../base/Icone";

const ICONES: NomeIcone[] = ["casa", "aviao", "capelo", "lista"];

interface Props {
  /** Nome da persona logada (ao vivo pelo BFF); sem login, o cliente demo. */
  nome?: string;
  onEscolher: (texto: string) => void;
  desabilitado: boolean;
  compacto?: boolean;
}

export function BoasVindas({ nome = "Fernando", onEscolher, desabilitado, compacto }: Props) {
  return (
    <div
      className="enter"
      style={{
        width: "100%",
        maxWidth: 760,
        margin: "auto",
        padding: compacto ? "24px 4px" : "32px 4px",
        display: "flex",
        flexDirection: "column",
        alignItems: compacto ? "flex-start" : "center",
        gap: compacto ? 20 : 28,
        textAlign: compacto ? "left" : "center",
        boxSizing: "border-box",
      }}
    >
      <span className={compacto ? "brand-mark lg" : "brand-mark xl"} aria-hidden="true">
        <Icone nome="bussola" tamanho={compacto ? "lg" : "xl"} />
      </span>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <h1 style={{ margin: 0, fontSize: compacto ? 32 : 44, lineHeight: compacto ? "38px" : "50px", fontWeight: 900, letterSpacing: "-.02em" }}>
          Oi, {nome}!
        </h1>
        <p style={{ margin: 0, fontSize: compacto ? 18 : 22, lineHeight: compacto ? "26px" : "32px", fontWeight: 600, color: "var(--ink-2)" }}>
          Eu sou a Bússola, da ia.i. Qual objetivo você quer tirar do papel?
        </p>
      </div>
      <div
        role="group"
        aria-label="Objetivos sugeridos"
        style={{
          width: "100%",
          maxWidth: 720,
          display: "grid",
          gridTemplateColumns: compacto ? "minmax(0, 1fr)" : "repeat(2, minmax(0, 1fr))",
          gap: compacto ? 10 : 14,
          textAlign: "left",
        }}
      >
        {SUGESTOES_INICIAIS.map((texto, i) => (
          <button
            key={texto}
            type="button"
            className="glass-card"
            disabled={desabilitado}
            onClick={() => onEscolher(texto)}
            style={{
              font: "inherit",
              color: "var(--ink)",
              cursor: desabilitado ? "wait" : "pointer",
              padding: compacto ? "12px 16px" : "18px 20px",
              minHeight: compacto ? 60 : undefined,
              display: "flex",
              alignItems: "center",
              gap: 14,
              borderRadius: 20,
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 44,
                height: 44,
                flexShrink: 0,
                borderRadius: 14,
                display: "grid",
                placeItems: "center",
                background: i === 0 ? "var(--accent-soft)" : "var(--row)",
                color: i === 0 ? "var(--accent-ink)" : "var(--ink-2)",
              }}
            >
              <Icone nome={ICONES[i] ?? "alvo"} />
            </span>
            <span style={{ fontSize: compacto ? 16 : 17, fontWeight: 800, lineHeight: "23px" }}>{texto}</span>
          </button>
        ))}
      </div>
      <p className="disclaimer" style={{ margin: 0, justifyContent: compacto ? "flex-start" : "center" }}>
        <Icone nome="escudo" tamanho="sm" />
        Eu analiso, simulo e recomendo. Qualquer ação só acontece com a sua autorização.
      </p>
    </div>
  );
}
