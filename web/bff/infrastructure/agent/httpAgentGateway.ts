// Gateway HTTP para a API do ADK (`adk web` / `get_fast_api_app`). No Cloud
// Run o agente é privado: cada chamada leva um ID token com audience = URL
// base do serviço. Numa URL de tag (main---<serviço>) o Cloud Run recusa essa
// audience (401), então `audience` passa a URL principal do serviço.
import { AgentUnavailable, NotFound } from "../../application/errors.ts";
import type { AgentGateway, AgentSession, AgentTurn } from "../../application/ports/agentGateway.ts";
import type { IdTokenProvider } from "../gcp/credentials.ts";

type Fetch = typeof fetch;

export interface HttpAgentGatewayOptions {
  baseUrl: string;
  /** Padrão: origem de `baseUrl`. */
  audience?: string;
  app: string;
  idTokens?: IdTokenProvider;
  fetch?: Fetch;
  timeoutMs?: number;
}

const APP_NAME = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;

function isSession(value: unknown): value is AgentSession {
  return typeof value === "object" && value !== null && typeof (value as { id?: unknown }).id === "string";
}

export class HttpAgentGateway implements AgentGateway {
  private readonly base: URL;
  private readonly audience: string;
  private readonly app: string;
  private readonly idTokens?: IdTokenProvider;
  private readonly fetch: Fetch;
  private readonly timeoutMs: number;

  constructor(options: HttpAgentGatewayOptions) {
    this.base = new URL(options.baseUrl);
    if (!["http:", "https:"].includes(this.base.protocol)) throw new Error("AGENT_URL deve ser http(s)");
    this.audience = options.audience ?? this.base.origin;
    if (!APP_NAME.test(options.app)) throw new Error("AGENT_APP inválido");
    this.app = options.app;
    this.idTokens = options.idTokens;
    this.fetch = options.fetch ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 15_000;
  }

  async createSession(userId: string, state: Record<string, unknown>): Promise<AgentSession> {
    const response = await this.call(this.sessionsPath(userId), {
      method: "POST",
      body: JSON.stringify({ state }),
    });
    if (!response.ok) throw new AgentUnavailable(`HTTP_${response.status}`);
    return this.session(response);
  }

  async getSession(userId: string, sessionId: string): Promise<AgentSession | null> {
    const response = await this.call(`${this.sessionsPath(userId)}/${encodeURIComponent(sessionId)}`, {
      method: "GET",
    });
    if (response.status === 404) return null;
    if (!response.ok) throw new AgentUnavailable(`HTTP_${response.status}`);
    return this.session(response);
  }

  async listSessions(userId: string): Promise<AgentSession[]> {
    const response = await this.call(this.sessionsPath(userId), { method: "GET" });
    if (!response.ok) throw new AgentUnavailable(`HTTP_${response.status}`);
    const body = (await response.json().catch(() => null)) as unknown;
    if (!Array.isArray(body)) throw new AgentUnavailable("LISTA_INVALIDA");
    // Sessão sem `id` não serve para retomar nada: sai da lista em silêncio.
    return body.filter((item): item is AgentSession => isSession(item));
  }

  async streamRun(turn: AgentTurn, signal: AbortSignal): Promise<AsyncIterable<Uint8Array>> {
    const response = await this.call(
      "/run_sse",
      {
        method: "POST",
        headers: { Accept: "text/event-stream" },
        body: JSON.stringify({
          appName: this.app,
          userId: turn.userId,
          sessionId: turn.sessionId,
          newMessage: { role: "user", parts: [{ text: turn.message.text }] },
          streaming: true,
        }),
      },
      signal,
    );
    if (!response.ok || !response.body) {
      await response.body?.cancel().catch(() => {});
      // O ADK procura a sessão por (app, userId, sessionId): 404 aqui é sessão
      // inexistente ou de outra persona, e não o agente fora do ar.
      if (response.status === 404) throw new NotFound();
      throw new AgentUnavailable(`HTTP_${response.status}`);
    }
    return response.body;
  }

  private sessionsPath(userId: string): string {
    return `/apps/${encodeURIComponent(this.app)}/users/${encodeURIComponent(userId)}/sessions`;
  }

  private async session(response: Response): Promise<AgentSession> {
    const body = (await response.json().catch(() => null)) as unknown;
    if (!isSession(body)) throw new AgentUnavailable("SESSAO_SEM_ID");
    return body;
  }

  /** `signal` presente: streaming, sem timeout total (o cliente decide quando parar). */
  private async call(path: string, init: RequestInit, signal?: AbortSignal): Promise<Response> {
    const headers = new Headers(init.headers);
    if (init.body) headers.set("Content-Type", "application/json");
    if (this.idTokens) headers.set("Authorization", `Bearer ${await this.idTokens.idToken(this.audience)}`);
    const url = new URL(path.replace(/^\//, ""), this.base.href.endsWith("/") ? this.base : `${this.base.href}/`);
    try {
      return await this.fetch(url, {
        ...init,
        headers,
        signal: signal ?? AbortSignal.timeout(this.timeoutMs),
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new AgentUnavailable("SEM_RESPOSTA");
    }
  }
}
