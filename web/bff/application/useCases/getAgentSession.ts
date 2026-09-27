import type { AuthSession } from "../../domain/authSession.ts";
import { NotFound } from "../errors.ts";
import type { AgentGateway, AgentSession } from "../ports/agentGateway.ts";

/** Lê a sessão do agente. Sessão de outro login responde como inexistente. */
export class GetAgentSession {
  private readonly agent: AgentGateway;

  constructor(agent: AgentGateway) {
    this.agent = agent;
  }

  async execute(session: AuthSession, agentSessionId: string): Promise<AgentSession> {
    if (!session.ownsAgentSession(agentSessionId)) throw new NotFound();
    const found = await this.agent.getSession(session.account.login, agentSessionId);
    if (!found) throw new NotFound();
    return found;
  }
}
