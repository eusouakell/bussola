// Parser incremental de `text/event-stream` (research R3): junta pedaços,
// separa blocos por linha em branco e devolve o `data:` de cada bloco.
import type { EventoAdk } from "./tipos";

function dadosDoBloco(bloco: string): string | null {
  const linhas = bloco
    .split("\n")
    .filter((l) => l.startsWith("data:"))
    .map((l) => l.slice(5).replace(/^ /, ""));
  return linhas.length > 0 ? linhas.join("\n") : null;
}

export class ParserSse {
  private buffer = "";

  /** Acrescenta um pedaço e devolve os `data:` dos blocos completos. */
  empurrar(pedaco: string): string[] {
    // `\r` só aparece como fim de linha; dentro do JSON ele vem escapado.
    this.buffer += pedaco.replace(/\r/g, "");
    const saida: string[] = [];
    let fim = this.buffer.indexOf("\n\n");
    while (fim >= 0) {
      const dados = dadosDoBloco(this.buffer.slice(0, fim));
      if (dados !== null) saida.push(dados);
      this.buffer = this.buffer.slice(fim + 2);
      fim = this.buffer.indexOf("\n\n");
    }
    return saida;
  }

  /** Fim do corpo: o último bloco pode chegar sem a linha em branco. */
  finalizar(): string[] {
    const dados = dadosDoBloco(this.buffer);
    this.buffer = "";
    return dados !== null ? [dados] : [];
  }
}

/** `data:` → evento do ADK; `{"error": …}` vira evento de erro; JSON inválido é ignorado. */
export function eventoDeDados(dados: string): EventoAdk | null {
  let valor: unknown;
  try {
    valor = JSON.parse(dados);
  } catch {
    return null;
  }
  if (!valor || typeof valor !== "object" || Array.isArray(valor)) return null;
  const obj = valor as Record<string, unknown>;
  if (obj.error !== undefined && obj.error !== null) {
    return { author: "sistema", error: typeof obj.error === "string" ? obj.error : "erro" };
  }
  return { ...(obj as unknown as EventoAdk), author: typeof obj.author === "string" ? obj.author : "bussola" };
}

/** Lê o corpo do `run_sse` e emite um evento por bloco completo. */
export async function* lerEventos(corpo: ReadableStream<Uint8Array>, sinal?: AbortSignal): AsyncIterable<EventoAdk> {
  const leitor = corpo.getReader();
  const decodificador = new TextDecoder();
  const parser = new ParserSse();
  try {
    while (!sinal?.aborted) {
      const { value, done } = await leitor.read();
      const blocos = done ? [...parser.empurrar(decodificador.decode()), ...parser.finalizar()] : parser.empurrar(decodificador.decode(value, { stream: true }));
      for (const dados of blocos) {
        if (sinal?.aborted) return;
        const evento = eventoDeDados(dados);
        if (evento) yield evento;
      }
      if (done) return;
    }
  } finally {
    leitor.releaseLock();
  }
}
