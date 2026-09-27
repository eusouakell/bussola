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
 */
export interface AgentGateway {
  createSession(userId: string, state: Readonly<Record<string, unknown>>): Promise<AgentSession>;
  getSession(userId: string, sessionId: string): Promise<AgentSession | null>;
  /** Eventos SSE do turno, em bytes, repassados sem alteração. */
  streamRun(turn: AgentTurn, signal: AbortSignal): Promise<AsyncIterable<Uint8Array>>;
}
