// Sessão de login simulado (entidade). O token é opaco e a sessão só guarda
// identidade e tempo. Quem é dono de uma sessão do agente é o próprio agente:
// a sessão vive lá sob o `login`, e ele responde 404 para a de outra persona.
// Guardar essa posse aqui trancaria a persona fora da própria conversa a cada
// reinício do BFF, que roda com uma instância só.
import type { UserAccount } from "./userAccount.ts";

export interface SessionPolicy {
  idleTtlMs: number;
  absoluteTtlMs: number;
}

export class AuthSession {
  readonly token: string;
  readonly account: UserAccount;
  readonly createdAt: number;
  private lastSeenAt: number;

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
}
