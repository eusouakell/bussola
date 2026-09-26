// Texto do agente com markdown mínimo (parágrafos, títulos "#", **negrito**,
// *itálico*, listas "- ", "* " e "1. ", separador "---"), montado em nós
// React: nada de HTML vindo do modelo.
import type { ReactNode } from "react";
import type { ItemMensagemAgente } from "../../sessao/modelo";
import { Tag } from "../base/Tag";

// Negrito, ou itálico sem espaço colado nos asteriscos ("2 * 3" fica como está).
const ENFASE = /(\*\*[^*\n]+\*\*|\*(?![\s*])[^*\n]+?(?<![\s*])\*)/g;

function emLinha(texto: string): ReactNode[] {
  return texto.split(ENFASE).map((parte, i) => {
    if (i % 2 === 0) return parte;
    return parte.startsWith("**") ? <strong key={i}>{parte.slice(2, -2)}</strong> : <em key={i}>{parte.slice(1, -1)}</em>;
  });
}

type TipoLinha = "texto" | "titulo" | "ul" | "ol";
interface Grupo {
  tipo: TipoLinha;
  linhas: string[];
  /** Número do primeiro item de uma lista numerada. */
  inicio?: number;
}

/** Classifica uma linha; `null` para o separador "---", que só quebra o fluxo. */
function classificar(linha: string): { tipo: TipoLinha; texto: string; numero?: number } | null {
  if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(linha)) return null;
  let m = /^\s{0,3}#{1,6}\s+(.*)$/.exec(linha);
  if (m) return { tipo: "titulo", texto: m[1] };
  m = /^\s*[-•*]\s+(.*)$/.exec(linha);
  if (m) return { tipo: "ul", texto: m[1] };
  m = /^\s*(\d{1,3})[.)]\s+(.*)$/.exec(linha);
  if (m) return { tipo: "ol", texto: m[2], numero: Number(m[1]) };
  return { tipo: "texto", texto: linha };
}

function agruparLinhas(texto: string): Grupo[] {
  const grupos: Grupo[] = [];
  for (const bloco of texto.split(/\n{2,}/)) {
    let anterior: Grupo | undefined;
    for (const bruta of bloco.split("\n")) {
      const l = classificar(bruta);
      if (!l) {
        anterior = undefined;
        continue;
      }
      if (l.tipo === "texto" && l.texto.trim() === "") continue;
      if (anterior?.tipo === l.tipo && l.tipo !== "titulo") {
        anterior.linhas.push(l.texto);
      } else {
        anterior = { tipo: l.tipo, linhas: [l.texto], inicio: l.numero };
        grupos.push(anterior);
      }
    }
  }
  return grupos;
}

const CURSOR = <span className="caret" aria-hidden="true" />;

export function blocosDeTexto(texto: string, cursor = false): ReactNode[] {
  const grupos = agruparLinhas(texto);
  return grupos.map((g, i) => {
    const fim = cursor && i === grupos.length - 1 ? CURSOR : null;
    if (g.tipo === "ul" || g.tipo === "ol") {
      const itens = g.linhas.map((l, j) => (
        <li key={j}>
          {emLinha(l)}
          {j === g.linhas.length - 1 && fim}
        </li>
      ));
      const estilo = { paddingLeft: 22, whiteSpace: "normal" } as const;
      return g.tipo === "ol" ? (
        <ol key={i} className="prose" start={g.inicio} style={estilo}>
          {itens}
        </ol>
      ) : (
        <ul key={i} className="prose" style={estilo}>
          {itens}
        </ul>
      );
    }
    return (
      <p key={i} className="prose">
        {g.tipo === "titulo" ? <strong>{emLinha(g.linhas[0])}</strong> : emLinha(g.linhas.join("\n"))}
        {fim}
      </p>
    );
  });
}

interface Props {
  item: ItemMensagemAgente;
}

export function MensagemAgente({ item }: Props) {
  const conteudo = blocosDeTexto(item.texto, item.emStreaming);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "0 4px" }}>
      {item.tag && (
        <span>
          <Tag tipo={item.tag} />
        </span>
      )}
      {conteudo.length === 0 && item.emStreaming ? (
        <span className="typing" role="status" aria-label="A Bússola está escrevendo">
          <span />
          <span />
          <span />
        </span>
      ) : (
        conteudo
      )}
    </div>
  );
}
