// Cria a sessão do agente para o login. O único state inicial é o
// `id_usuario` da conta: o navegador não escolhe de quem são os dados.
import type { AuthSession, SessionPolicy } from "../../domain/authSession.ts";
import type { AgentGateway, AgentSession } from "../ports/agentGateway.ts";
import type { Logger } from "../ports/logger.ts";

export interface StartAgentSessionDeps {
  agent: AgentGateway;
  policy: SessionPolicy;
  logger: Logger;
}

export class StartAgentSession {
  private readonly deps: StartAgentSessionDeps;

  constructor(deps: StartAgentSessionDeps) {
    this.deps = deps;
  }

  async execute(session: AuthSession): Promise<AgentSession> {
    const { agent, policy, logger } = this.deps;
    const { login, idUsuario } = session.account;
    const created = await agent.createSession(login, { id_usuario: idUsuario });
    session.bindAgentSession(created.id, policy);
    logger.info("sessão do agente criada", { evento: "sessao_criada", session_id: created.id, id_usuario: idUsuario });
    return created;
  }
}
