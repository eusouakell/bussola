// Transporte ao vivo (contracts/eventos-agente.md §1): sessão no ADK,
// `run_sse` com streaming e ressincronização do state depois do turno.
//
// A sessão do ADK é o histórico do chat. O id da conversa corrente fica
// lembrado no navegador (por app e persona), então recarregar a página volta
// para a mesma conversa em vez de abrir uma vazia — desde que o agente rode
// com um backend de sessão que sobreviva ao cold start (`ADK_SESSION_URI`).
import { CONFIG } from "../config";
import { lerEventos } from "./sse";
import type { EstadoSessao, EventoAdk } from "./tipos";
import { FalhaConexao, type InicioSessao, type ResumoConversa, type Transporte } from "./transporte";

/** Onde o id da conversa corrente fica lembrado entre recargas. */
export interface MemoriaConversa {
  ler(): string | null;
  gravar(sessionId: string): void;
  limpar(): void;
}

/**
 * `localStorage`, quando existe e deixa escrever (aba privada, cookies
 * bloqueados e SSR caem para memória volátil: a conversa continua no agente,
 * só não é lembrada).
 */
export function memoriaLocal(chave: string): MemoriaConversa {
  let volatil: string | null = null;
  const loja = (): Storage | null => {
    try {
      return globalThis.localStorage ?? null;
    } catch {
      return null;
    }
  };
  return {
    ler() {
      try {
        return loja()?.getItem(chave) ?? volatil;
      } catch {
        return volatil;
      }
    },
    gravar(sessionId) {
      volatil = sessionId;
      try {
        loja()?.setItem(chave, sessionId);
      } catch {
        // Sem persistência: só a memória volátil desta aba.
      }
    },
    limpar() {
      volatil = null;
      try {
        loja()?.removeItem(chave);
      } catch {
        // idem
      }
    },
  };
}

export interface OpcoesAdk {
  app: string;
  usuario: string;
  /** Prefixo das rotas (padrão: `CONFIG.baseApi`; vazio usa o proxy do Vite em dev). */
  base?: string;
  fetch?: typeof fetch;
  /** Padrão: `localStorage` por app e persona. */
  memoria?: MemoriaConversa;
}

interface CorpoSessao {
  id?: unknown;
  state?: EstadoSessao;
  events?: unknown;
  lastUpdateTime?: unknown;
}

function tituloDe(estado: EstadoSessao | undefined): string | undefined {
  const descricao = estado?.objetivo?.descricao;
  return typeof descricao === "string" && descricao.trim() ? descricao.trim() : undefined;
}

export class ClienteAdk implements Transporte {
  readonly modo = "ao-vivo" as const;
  private sessionId: string | null = null;
  private readonly opcoes: OpcoesAdk;
  private readonly memoria: MemoriaConversa;

  constructor(opcoes: OpcoesAdk) {
    this.opcoes = opcoes;
    this.memoria = opcoes.memoria ?? memoriaLocal(`bussola.conversa.${opcoes.app}.${opcoes.usuario}`);
  }

  private buscar(caminho: string, init?: RequestInit): Promise<Response> {
    const f = this.opcoes.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
    return f(`${this.opcoes.base ?? CONFIG.baseApi}${caminho}`, init);
  }

  private get caminhoSessoes(): string {
    return `${CONFIG.rotasAdk.apps}/${encodeURIComponent(this.opcoes.app)}/users/${encodeURIComponent(this.opcoes.usuario)}/sessions`;
  }

  /** Retoma a conversa lembrada; se ela não existe mais, abre uma nova. */
  async iniciar(): Promise<InicioSessao> {
    const lembrada = this.memoria.ler();
    if (lembrada) {
      const anterior = await this.carregar(lembrada).catch(() => null);
      if (anterior) return this.adotar(anterior, true);
      // Conversa apagada, de outra persona ou perdida num cold start.
      this.memoria.limpar();
    }
    return this.adotar(await this.criar(), false);
  }

  async retomar(sessionId: string): Promise<InicioSessao> {
    const corpo = await this.carregar(sessionId);
    if (!corpo) throw new FalhaConexao("conversa inexistente");
    return this.adotar(corpo, true);
  }

  async listar(): Promise<ResumoConversa[]> {
    let resposta: Response;
    try {
      resposta = await this.buscar(this.caminhoSessoes);
    } catch {
      throw new FalhaConexao("rede");
    }
    if (!resposta.ok) throw new FalhaConexao(`http ${resposta.status}`);
    let corpo: unknown;
    try {
      corpo = await resposta.json();
    } catch {
      throw new FalhaConexao("corpo inválido");
    }
    if (!Array.isArray(corpo)) throw new FalhaConexao("lista inválida");
    return corpo
      .filter((item): item is CorpoSessao => typeof item === "object" && item !== null && typeof (item as CorpoSessao).id === "string")
      .map((item) => ({
        sessionId: item.id as string,
        // O ADK devolve segundos; a tela trabalha em milissegundos.
        atualizadaEm: typeof item.lastUpdateTime === "number" ? item.lastUpdateTime * 1000 : undefined,
        titulo: tituloDe(item.state),
      }));
  }

  esquecer(): void {
    this.memoria.limpar();
    this.sessionId = null;
  }

  async *enviar(texto: string, sinal?: AbortSignal): AsyncIterable<EventoAdk> {
    if (!this.sessionId) throw new FalhaConexao("sem sessão");
    let resposta: Response;
    try {
      resposta = await this.buscar(CONFIG.rotasAdk.runSse, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({
          appName: this.opcoes.app,
          userId: this.opcoes.usuario,
          sessionId: this.sessionId,
          newMessage: { role: "user", parts: [{ text: texto }] },
          streaming: true,
        }),
        signal: sinal,
      });
    } catch {
      if (sinal?.aborted) return;
      throw new FalhaConexao("rede");
    }
    if (!resposta.ok || !resposta.body) throw new FalhaConexao(`http ${resposta.status}`);
    try {
      yield* lerEventos(resposta.body, sinal);
    } catch {
      if (sinal?.aborted) return;
      throw new FalhaConexao("fluxo interrompido");
    }
  }

  async ressincronizar(): Promise<EstadoSessao | null> {
    if (!this.sessionId) return null;
    const corpo = await this.carregar(this.sessionId).catch(() => null);
    return corpo?.state ?? null;
  }

  private async criar(): Promise<CorpoSessao> {
    let resposta: Response;
    try {
      resposta = await this.buscar(this.caminhoSessoes, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
    } catch {
      throw new FalhaConexao("rede");
    }
    if (!resposta.ok) throw new FalhaConexao(`http ${resposta.status}`);
    return await this.corpo(resposta);
  }

  /** `null` quando a conversa não está mais lá (404 ou corpo sem id). */
  private async carregar(sessionId: string): Promise<CorpoSessao | null> {
    let resposta: Response;
    try {
      resposta = await this.buscar(`${this.caminhoSessoes}/${encodeURIComponent(sessionId)}`);
    } catch {
      throw new FalhaConexao("rede");
    }
    if (resposta.status === 404) return null;
    if (!resposta.ok) throw new FalhaConexao(`http ${resposta.status}`);
    return await this.corpo(resposta).catch(() => null);
  }

  private async corpo(resposta: Response): Promise<CorpoSessao> {
    let corpo: CorpoSessao;
    try {
      corpo = (await resposta.json()) as CorpoSessao;
    } catch {
      throw new FalhaConexao("corpo inválido");
    }
    if (typeof corpo?.id !== "string") throw new FalhaConexao("sessão sem id");
    return corpo;
  }

  private adotar(corpo: CorpoSessao, retomada: boolean): InicioSessao {
    const sessionId = corpo.id as string;
    this.sessionId = sessionId;
    this.memoria.gravar(sessionId);
    const eventos = Array.isArray(corpo.events) ? (corpo.events as EventoAdk[]) : [];
    return { sessionId, estado: corpo.state ?? {}, eventos: retomada ? eventos : [], retomada };
  }
}
