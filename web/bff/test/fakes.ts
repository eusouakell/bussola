// Dublês das portas para testar casos de uso sem infraestrutura.
import { NotFound } from "../application/errors.ts";
import type { AgentGateway, AgentSession, AgentTurn } from "../application/ports/agentGateway.ts";
import type { LogFields, Logger } from "../application/ports/logger.ts";
import type { LoginRateLimiter } from "../application/ports/loginRateLimiter.ts";
import type { PasswordVerifier } from "../application/ports/passwordVerifier.ts";
import type { SessionRepository } from "../application/ports/sessionRepository.ts";
import type { UserRepository } from "../application/ports/userRepository.ts";
import { AuthSession } from "../domain/authSession.ts";
import type { UserAccount } from "../domain/userAccount.ts";

export class FakeUserRepository implements UserRepository {
  readonly accounts: UserAccount[];

  constructor(accounts: UserAccount[]) {
    this.accounts = accounts;
  }

  async findByLogin(login: string): Promise<UserAccount | null> {
    return this.accounts.find((item) => item.login === login) ?? null;
  }

  async listFeatured(): Promise<UserAccount[]> {
    return this.accounts.filter((item) => item.featured);
  }
}

export class FakePasswordVerifier implements PasswordVerifier {
  readonly password: string;
  calls = 0;

  constructor(password: string) {
    this.password = password;
  }

  async verify(password: unknown): Promise<boolean> {
    this.calls += 1;
    return password === this.password;
  }
}

export class FakeSessionRepository implements SessionRepository {
  readonly sessions = new Map<string, AuthSession>();
  readonly now: () => number;
  private counter = 0;

  constructor(now: () => number = Date.now) {
    this.now = now;
  }

  async create(account: UserAccount): Promise<AuthSession> {
    this.counter += 1;
    const session = new AuthSession(`token-${this.counter}`, account, this.now());
    this.sessions.set(session.token, session);
    return session;
  }

  async find(token: string): Promise<AuthSession | null> {
    return this.sessions.get(token) ?? null;
  }

  async revoke(token: string): Promise<void> {
    this.sessions.delete(token);
  }
}

export class FakeRateLimiter implements LoginRateLimiter {
  blocked = false;
  readonly failures: string[][] = [];
  readonly resets: string[] = [];

  isBlocked(): boolean {
    return this.blocked;
  }

  recordFailure(keys: readonly string[]): void {
    this.failures.push([...keys]);
  }

  reset(key: string): void {
    this.resets.push(key);
  }
}

/** Como o ADK, guarda a sessão sob o `userId`: só ele a encontra. */
export class FakeAgentGateway implements AgentGateway {
  readonly created: { userId: string; state: Readonly<Record<string, unknown>> }[] = [];
  readonly turns: AgentTurn[] = [];
  readonly sessions = new Map<string, AgentSession>();
  private counter = 0;

  async createSession(userId: string, state: Readonly<Record<string, unknown>>): Promise<AgentSession> {
    this.counter += 1;
    const session = { id: `agente-${this.counter}`, userId, state, lastUpdateTime: this.counter, events: [] };
    this.created.push({ userId, state });
    this.sessions.set(key(userId, session.id), session);
    return session;
  }

  async getSession(userId: string, sessionId: string): Promise<AgentSession | null> {
    return this.sessions.get(key(userId, sessionId)) ?? null;
  }

  async listSessions(userId: string): Promise<AgentSession[]> {
    return [...this.sessions.entries()]
      .filter(([chave]) => chave.startsWith(`${userId}\u0000`))
      .map(([, session]) => session);
  }

  async streamRun(turn: AgentTurn): Promise<AsyncIterable<Uint8Array>> {
    if (!this.sessions.has(key(turn.userId, turn.sessionId))) throw new NotFound();
    this.turns.push(turn);
    return events('data: {"ok":true}\n\n');
  }
}

/** `\u0000` não aparece num login nem num id de sessão. */
function key(userId: string, sessionId: string): string {
  return `${userId}\u0000${sessionId}`;
}

async function* events(...chunks: string[]): AsyncIterable<Uint8Array> {
  for (const chunk of chunks) yield new TextEncoder().encode(chunk);
}

export interface LogEntry extends LogFields {
  level: "info" | "warn" | "error";
  message: string;
}

export class RecordingLogger implements Logger {
  readonly entries: LogEntry[] = [];

  info(message: string, fields: LogFields = {}): void {
    this.entries.push({ level: "info", message, ...fields });
  }

  warn(message: string, fields: LogFields = {}): void {
    this.entries.push({ level: "warn", message, ...fields });
  }

  error(message: string, fields: LogFields = {}): void {
    this.entries.push({ level: "error", message, ...fields });
  }

  events(): (string | undefined)[] {
    return this.entries.map((entry) => entry.evento);
  }
}
