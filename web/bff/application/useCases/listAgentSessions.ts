// Conversas salvas da persona logada. O `login` do cookie é o `userId` da
// busca, então uma persona nunca vê a conversa de outra.
import type { AuthSession } from "../../domain/authSession.ts";
import type { AgentGateway, AgentSession } from "../ports/agentGateway.ts";

/** Resumo de uma conversa: o mesmo formato do ADK, sem o histórico. */
export interface AgentSessionSummary {
  id: string;
  lastUpdateTime?: number;
  state?: Record<string, unknown>;
}

function summarize(session: AgentSession): AgentSessionSummary {
  const { id, lastUpdateTime, state } = session as AgentSessionSummary;
  return {
    id,
    // Sessão nova em alguns backends não tem horário: o front cai no "sem data".
    ...(typeof lastUpdateTime === "number" ? { lastUpdateTime } : {}),
    ...(state && typeof state === "object" ? { state } : {}),
  };
}

/**
 * Lista as conversas para o seletor do front. `events` fica de fora: a lista é
 * para escolher, e o histórico só vem no GET da conversa escolhida.
 */
export class ListAgentSessions {
  private readonly agent: AgentGateway;

  constructor(agent: AgentGateway) {
    this.agent = agent;
  }

  async execute(session: AuthSession): Promise<AgentSessionSummary[]> {
    const sessions = await this.agent.listSessions(session.account.login);
    // Mais recente primeiro: é a conversa que o cliente quer retomar.
    return sessions.map(summarize).sort((a, b) => (b.lastUpdateTime ?? 0) - (a.lastUpdateTime ?? 0));
  }
}
