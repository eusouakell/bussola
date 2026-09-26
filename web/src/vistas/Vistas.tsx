// Vistas de produto P1–P5 (T053): leem o plano criado na conversa, sem
// roteador. Os dados vêm de `modelo.estado` e das últimas respostas de
// ferramentas em `modelo.itens` (FR-024); nada é calculado aqui (FR-007).
import type { JSX } from "react";
import { Icone, type NomeIcone } from "../componentes/base/Icone";
import { SeloSintetico } from "../componentes/base/SeloSintetico";
import type { ModeloSessao } from "../sessao/modelo";
import { lerPlano } from "./dados";
import { EstadoVazio } from "./EstadoVazio";
import { P1Encerramento } from "./P1Encerramento";
import { P2MeuPlano } from "./P2MeuPlano";
import { P3Trilha } from "./P3Trilha";
import { P4Resumo } from "./P4Resumo";
import { P5CheckIn } from "./P5CheckIn";

export type NomeVista = "encerramento" | "meu-plano" | "trilha" | "resumo" | "check-in";

/** Ordem de navegação e rótulos (pt-BR). */
export const VISTAS: { nome: NomeVista; rotulo: string }[] = [
  { nome: "encerramento", rotulo: "Jornada" },
  { nome: "meu-plano", rotulo: "Meu plano" },
  { nome: "trilha", rotulo: "Trilha" },
  { nome: "resumo", rotulo: "Resumo" },
  { nome: "check-in", rotulo: "Check-in" },
];

const TITULOS: Record<NomeVista, string> = {
  encerramento: "Jornada concluída",
  "meu-plano": "Meu plano",
  trilha: "Trilha",
  resumo: "Resumo do plano",
  "check-in": "Check-in do mês",
};

const ICONES: Record<NomeVista, NomeIcone> = {
  encerramento: "estrela",
  "meu-plano": "alvo",
  trilha: "trilha",
  resumo: "lista",
  "check-in": "calendario",
};

interface Props {
  vista: NomeVista;
  modelo: ModeloSessao;
  /** Navegação local, sem roteador. */
  onVista: (v: NomeVista) => void;
  /** Volta para a conversa. */
  onConversa: () => void;
  /** O App volta à conversa e envia o texto ao agente. */
  onEnviar: (texto: string) => void;
}

export function Vistas({ vista, modelo, onVista, onConversa, onEnviar }: Props): JSX.Element {
  const plano = lerPlano(modelo);

  let conteudo: JSX.Element;
  if (!plano) conteudo = <EstadoVazio onConversa={onConversa} />;
  else if (vista === "encerramento") conteudo = <P1Encerramento plano={plano} onVista={onVista} onEnviar={onEnviar} />;
  else if (vista === "meu-plano") conteudo = <P2MeuPlano plano={plano} onVista={onVista} onEnviar={onEnviar} />;
  else if (vista === "trilha") conteudo = <P3Trilha plano={plano} onEnviar={onEnviar} />;
  else if (vista === "resumo") conteudo = <P4Resumo plano={plano} />;
  else conteudo = <P5CheckIn plano={plano} ateAnomes={modelo.estado.ate_anomes} onEnviar={onEnviar} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: "1 1 auto", minHeight: 0, height: "100%" }}>
      <header
        className="glass-chrome"
        style={{ height: 56, borderRadius: 20, display: "flex", alignItems: "center", gap: 8, padding: "0 6px", flexShrink: 0 }}
      >
        <button type="button" className="icon-btn" aria-label="Voltar para a conversa" onClick={onConversa} style={{ border: 0 }}>
          <Icone nome="voltar" />
        </button>
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.15, flex: "1 1 auto", minWidth: 0 }}>
          <h1 style={{ margin: 0, fontSize: 17, fontWeight: 900, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {TITULOS[vista]}
          </h1>
          <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-3)" }}>Bússola · ia.i</span>
        </div>
        <SeloSintetico compacto />
      </header>

      <div key={vista} style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto" }}>
        <div style={{ maxWidth: 560, margin: "0 auto", display: "flex", flexDirection: "column", gap: 12, paddingBottom: 4 }}>{conteudo}</div>
      </div>

      {plano && (
        <nav
          aria-label="Seções do plano"
          style={{
            flexShrink: 0,
            width: "100%",
            maxWidth: 560,
            margin: "0 auto",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(96px, 1fr))",
            gap: 8,
          }}
        >
          {VISTAS.filter((v) => v.nome !== vista).map((v) => (
            <BotaoSecao key={v.nome} icone={ICONES[v.nome]} rotulo={v.rotulo} onClick={() => onVista(v.nome)} />
          ))}
          <BotaoSecao icone="conversa" rotulo="Conversar" onClick={onConversa} />
        </nav>
      )}
    </div>
  );
}

function BotaoSecao({ icone, rotulo, onClick }: { icone: NomeIcone; rotulo: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className="glass-chrome"
      onClick={onClick}
      style={{
        font: "inherit",
        color: "var(--ink)",
        cursor: "pointer",
        borderRadius: 16,
        minHeight: 56,
        padding: "8px 6px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 4,
        fontSize: 13.5,
        fontWeight: 800,
      }}
    >
      <Icone nome={icone} tamanho="sm" />
      {rotulo}
    </button>
  );
}
