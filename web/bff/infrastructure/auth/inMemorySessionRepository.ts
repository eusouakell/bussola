// Sessões de login em memória (o serviço roda com uma instância só). Token
// opaco de 256 bits. Ao criar, limpa as expiradas e, cheio, descarta a mais
// antiga.
import { randomBytes } from "node:crypto";
import type { SessionRepository } from "../../application/ports/sessionRepository.ts";
import { AuthSession, type SessionPolicy } from "../../domain/authSession.ts";
import type { UserAccount } from "../../domain/userAccount.ts";

export interface InMemorySessionRepositoryOptions {
  maxSessions: number;
  policy: SessionPolicy;
  now?: () => number;
}

export class InMemorySessionRepository implements SessionRepository {
  private readonly sessions = new Map<string, AuthSession>();
  private readonly maxSessions: number;
  private readonly policy: SessionPolicy;
  private readonly now: () => number;

  constructor(options: InMemorySessionRepositoryOptions) {
    this.maxSessions = options.maxSessions;
    this.policy = options.policy;
    this.now = options.now ?? Date.now;
  }

  async create(account: UserAccount): Promise<AuthSession> {
    this.evict();
    const session = new AuthSession(randomBytes(32).toString("base64url"), account, this.now());
    this.sessions.set(session.token, session);
    return session;
  }

  async find(token: string): Promise<AuthSession | null> {
    return this.sessions.get(token) ?? null;
  }

  async revoke(token: string): Promise<void> {
    this.sessions.delete(token);
  }

  get size(): number {
    return this.sessions.size;
  }

  private evict(): void {
    const now = this.now();
    for (const [token, session] of this.sessions) {
      if (session.isExpired(this.policy, now)) this.sessions.delete(token);
    }
    while (this.sessions.size >= this.maxSessions) {
      const oldest = this.sessions.keys().next().value;
      if (oldest === undefined) break;
      this.sessions.delete(oldest);
    }
  }
}
