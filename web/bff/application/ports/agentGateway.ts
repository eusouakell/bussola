import type { ChatMessage } from "../../domain/chatMessage.ts";

/** Sessão do ADK como o agente devolve (`id`, `state`, `events`...). */
export interface AgentSession {
  id: string;
  [field: string]: unknown;
}

export interface AgentTurn {
  userId: string;
  sessionId: string;
  message: ChatMessage;
}

/**
 * Agente ADK. O adapter monta sempre o corpo das chamadas: nada que o
 * navegador mande (state, stateDelta, userId, appName) chega ao agente.
 * Falhas de rede ou HTTP viram `AgentUnavailable`.
 *
 * O agente guarda cada sessão sob o `userId`, então é ele quem decide a posse:
 * `userId` que não é dono do `sessionId` não encontra a sessão.
 */
export interface AgentGateway {
  createSession(userId: string, state: Readonly<Record<string, unknown>>): Promise<AgentSession>;
  /** `null` quando não existe nenhuma sessão com esse id para esse `userId`. */
  getSession(userId: string, sessionId: string): Promise<AgentSession | null>;
  /** Conversas desse `userId`, como o agente as guarda (sem os eventos). */
  listSessions(userId: string): Promise<AgentSession[]>;
  /**
   * Eventos SSE do turno, em bytes, repassados sem alteração. Sessão que não
   * existe para esse `userId` é `NotFound`, não `AgentUnavailable`.
   */
  streamRun(turn: AgentTurn, signal: AbortSignal): Promise<AsyncIterable<Uint8Array>>;
}
