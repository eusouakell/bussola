// Sessão de login simulado (entidade). O token é opaco; a sessão guarda quais
// sessões do agente pertencem ao login, para que uma persona não leia nem
// escreva na sessão de outra.
import type { UserAccount } from "./userAccount.ts";

export interface SessionPolicy {
  idleTtlMs: number;
  absoluteTtlMs: number;
  maxAgentSessions: number;
}

export class AuthSession {
  readonly token: string;
  readonly account: UserAccount;
  readonly createdAt: number;
  private lastSeenAt: number;
  private readonly agentSessionIds = new Set<string>();

  constructor(token: string, account: UserAccount, now: number) {
    this.token = token;
    this.account = account;
    this.createdAt = now;
    this.lastSeenAt = now;
  }

  isExpired(policy: SessionPolicy, now: number): boolean {
    return now - this.lastSeenAt > policy.idleTtlMs || now - this.createdAt > policy.absoluteTtlMs;
  }

  touch(now: number): void {
    this.lastSeenAt = now;
  }

  /** Registra a sessão do agente; acima do limite, esquece a mais antiga. */
  bindAgentSession(agentSessionId: string, policy: SessionPolicy): void {
    this.agentSessionIds.add(agentSessionId);
    while (this.agentSessionIds.size > policy.maxAgentSessions) {
      const oldest = this.agentSessionIds.values().next().value;
      if (oldest === undefined) break;
      this.agentSessionIds.delete(oldest);
    }
  }

  ownsAgentSession(agentSessionId: unknown): agentSessionId is string {
    return typeof agentSessionId === "string" && this.agentSessionIds.has(agentSessionId);
  }
}
