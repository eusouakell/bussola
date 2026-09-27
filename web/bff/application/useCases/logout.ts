import type { SessionRepository } from "../ports/sessionRepository.ts";

export class Logout {
  private readonly sessions: SessionRepository;

  constructor(sessions: SessionRepository) {
    this.sessions = sessions;
  }

  async execute(token: string | undefined): Promise<void> {
    if (token) await this.sessions.revoke(token);
  }
}
