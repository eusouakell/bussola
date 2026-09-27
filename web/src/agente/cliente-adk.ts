// Transporte ao vivo (contracts/eventos-agente.md §1): sessão no ADK,
// `run_sse` com streaming e ressincronização do state depois do turno.
import { CONFIG } from "../config";
import { lerEventos } from "./sse";
import type { EstadoSessao, EventoAdk } from "./tipos";
import { FalhaConexao, type InicioSessao, type Transporte } from "./transporte";

export interface OpcoesAdk {
  app: string;
  usuario: string;
  /** Prefixo das rotas (padrão: `CONFIG.baseApi`; vazio usa o proxy do Vite em dev). */
  base?: string;
  fetch?: typeof fetch;
}

export class ClienteAdk implements Transporte {
  readonly modo = "ao-vivo" as const;
  private sessionId: string | null = null;
  private readonly opcoes: OpcoesAdk;

  constructor(opcoes: OpcoesAdk) {
    this.opcoes = opcoes;
  }

  private buscar(caminho: string, init?: RequestInit): Promise<Response> {
    const f = this.opcoes.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
    return f(`${this.opcoes.base ?? CONFIG.baseApi}${caminho}`, init);
  }

  private get caminhoSessoes(): string {
    return `${CONFIG.rotasAdk.apps}/${encodeURIComponent(this.opcoes.app)}/users/${encodeURIComponent(this.opcoes.usuario)}/sessions`;
  }

  async iniciar(): Promise<InicioSessao> {
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
    let corpo: { id?: unknown; state?: EstadoSessao };
    try {
      corpo = (await resposta.json()) as typeof corpo;
    } catch {
      throw new FalhaConexao("corpo inválido");
    }
    if (typeof corpo?.id !== "string") throw new FalhaConexao("sessão sem id");
    this.sessionId = corpo.id;
    return { sessionId: corpo.id, estado: corpo.state ?? {}, eventos: [] };
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
    try {
      const resposta = await this.buscar(`${this.caminhoSessoes}/${encodeURIComponent(this.sessionId)}`);
      if (!resposta.ok) return null;
      const corpo = (await resposta.json()) as { state?: EstadoSessao };
      return corpo.state ?? null;
    } catch {
      return null;
    }
  }
}
