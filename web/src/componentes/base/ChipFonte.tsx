// Fonte do dado (FR-008): ferramenta, tabelas, período e avisos do envelope de origem.
import { useEffect, useId, useRef, useState } from "react";
import type { Fonte } from "../../agente/tipos";
import { periodo } from "../../formatacao/formatar";
import { nomeLegivel } from "../../sessao/catalogo";
import { Icone } from "./Icone";

interface Props {
  fonte: Fonte | undefined;
  avisos?: string[];
  /** Texto do chip; padrão "Nome legível · período". */
  rotulo?: string;
  /** Só o ícone (chips em cantos apertados). */
  compacto?: boolean;
}

export function rotuloFonte(fonte: Fonte): string {
  const nome = nomeLegivel(fonte.ferramenta);
  return fonte.periodo ? `${nome} · ${periodo(fonte.periodo)}` : nome;
}

export function ChipFonte({ fonte, avisos, rotulo, compacto }: Props) {
  const [aberto, setAberto] = useState(false);
  const raiz = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) setAberto(false);
    };
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAberto(false);
    };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", tecla);
    };
  }, [aberto]);

  if (!fonte) return null;
  const texto = rotulo ?? rotuloFonte(fonte);

  return (
    <span className="fonte-wrap" ref={raiz}>
      <button
        type="button"
        className={aberto ? "chip-fonte on" : "chip-fonte"}
        aria-expanded={aberto}
        aria-controls={id}
        aria-label={compacto ? `Fonte: ${texto}` : undefined}
        style={compacto ? { padding: "0 8px" } : undefined}
        onClick={() => setAberto((a) => !a)}
      >
        <Icone nome="db" tamanho="sm" />
        {!compacto && texto}
      </button>
      {aberto && (
        <div className="popover" role="dialog" aria-label="Fonte do dado" id={id}>
          <div className="row-between">
            <span className="eyebrow">Fonte do dado</span>
            <button type="button" className="link-btn" aria-label="Fechar" style={{ color: "var(--ink-3)" }} onClick={() => setAberto(false)}>
              <Icone nome="x" tamanho="sm" />
            </button>
          </div>
          <div className="pop-row">
            <span className="k">Ferramenta</span>
            <span style={{ fontWeight: 800 }}>{nomeLegivel(fonte.ferramenta)}</span>
          </div>
          <div className="pop-row">
            <span className="k">Tabelas</span>
            {fonte.tabelas.length > 0 ? (
              <span className="mono" style={{ lineHeight: "19px" }}>
                {fonte.tabelas.map((t) => (
                  <span key={t} style={{ display: "block" }}>
                    {t}
                  </span>
                ))}
              </span>
            ) : (
              <span style={{ fontWeight: 700, color: "var(--ink-3)" }}>Nenhuma (ferramenta local)</span>
            )}
          </div>
          <div className="pop-row">
            <span className="k">Período</span>
            <span className="num" style={{ fontWeight: 700 }}>
              {periodo(fonte.periodo)}
            </span>
          </div>
          <div className="pop-row">
            <span className="k">Avisos</span>
            {avisos && avisos.length > 0 ? (
              <span style={{ fontWeight: 700, color: "var(--warn)" }}>
                {avisos.map((a) => (
                  <span key={a} style={{ display: "block" }}>
                    {a}
                  </span>
                ))}
              </span>
            ) : (
              <span style={{ fontWeight: 700, color: "var(--ink-3)" }}>Nenhum</span>
            )}
          </div>
          <div className="hline" />
          <span className="disclaimer">
            <Icone nome="frasco" tamanho="sm" />
            Dados sintéticos · cálculo determinístico
          </span>
        </div>
      )}
    </span>
  );
}
