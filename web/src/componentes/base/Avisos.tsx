import { Icone } from "./Icone";

interface Props {
  avisos: string[] | undefined;
}

const SIMULADA = /^Resposta simulada pelo front; regravar após o ciclo (\d{3})$/;

/**
 * Aviso de demonstração (números de exemplo, simulação de exemplo): peso de
 * badge, nunca de alerta de negócio (BUG-06). Tolerante à redação do backend.
 */
const DEMONSTRACAO = /\bde exemplo\b|\b(?:desta|nesta|da) demonstra[çc][ãa]o\b/i;

/**
 * Jargão interno que não pode chegar ao cliente de jeito nenhum: se escapar do
 * backend, o aviso é descartado em vez de virar texto na tela (BUG-06).
 */
const JARGAO = /\bmock|valor_alvo\s*=|prazo_meses\s*=|corte\s+\d{6}/i;

function ehDemonstracao(aviso: string): boolean {
  return SIMULADA.test(aviso) || DEMONSTRACAO.test(aviso);
}

/** Texto curto do badge; o aviso do front traz o ciclo. */
function rotuloDemonstracao(aviso: string): string {
  const simulada = SIMULADA.exec(aviso);
  return simulada ? `Resposta simulada pelo front · ciclo ${simulada[1]}` : aviso;
}

/** `avisos` do envelope como alerta âmbar, nunca como erro (FR-009). */
export function Avisos({ avisos }: Props) {
  // Dedup na lista inteira: o mesmo aviso não repete nem duplica chave React (BUG-05b).
  const unicos = [...new Set(avisos ?? [])].filter((a) => !JARGAO.test(a));
  const alertas = unicos.filter((a) => !ehDemonstracao(a));
  const demonstracoes = unicos.filter(ehDemonstracao);
  if (alertas.length === 0 && demonstracoes.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-start" }} aria-label="Avisos da consulta">
      {alertas.map((aviso) => (
        <div
          key={aviso}
          className="note note-warn"
          style={{ fontSize: 14, lineHeight: "19px", padding: "9px 12px", alignSelf: "stretch" }}
        >
          <Icone nome="alerta" />
          <span>{aviso}</span>
        </div>
      ))}
      {demonstracoes.map((aviso) => (
        <span
          key={aviso}
          className="badge badge-warn"
          title={aviso}
          // `whiteSpace` liberado: o texto do backend é maior que o do front e
          // não pode estourar o card em tela estreita.
          style={{ minHeight: 24, fontSize: 12, whiteSpace: "normal", padding: "3px 11px 3px 8px", maxWidth: "100%" }}
        >
          <Icone nome="frasco" tamanho="sm" />
          {rotuloDemonstracao(aviso)}
        </span>
      ))}
    </div>
  );
}
