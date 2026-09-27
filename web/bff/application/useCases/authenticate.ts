// Resolve o token do cookie em sessão válida. Expira por inatividade e por
// prazo absoluto; cada uso renova a inatividade.
import type { AuthSession, SessionPolicy } from "../../domain/authSession.ts";
import { NotAuthenticated } from "../errors.ts";
import type { SessionRepository } from "../ports/sessionRepository.ts";

export interface AuthenticateDeps {
  sessions: SessionRepository;
  policy: SessionPolicy;
  now?: () => number;
}

export class Authenticate {
  private readonly sessions: SessionRepository;
  private readonly policy: SessionPolicy;
  private readonly now: () => number;

  constructor(deps: AuthenticateDeps) {
    this.sessions = deps.sessions;
    this.policy = deps.policy;
    this.now = deps.now ?? Date.now;
  }

  async execute(token: string | undefined): Promise<AuthSession> {
    if (!token) throw new NotAuthenticated();
    const session = await this.sessions.find(token);
    if (!session) throw new NotAuthenticated();
    const now = this.now();
    if (session.isExpired(this.policy, now)) {
      await this.sessions.revoke(token);
      throw new NotAuthenticated();
    }
    session.touch(now);
    return session;
  }
}
