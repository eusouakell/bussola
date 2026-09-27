import type { IncomingMessage } from "node:http";
import type { Authenticate } from "../../application/useCases/authenticate.ts";
import type { AuthSession } from "../../domain/authSession.ts";
import type { SessionCookie } from "./cookies.ts";

/** Sessão de login do pedido, a partir do cookie. Sem sessão válida: 401. */
export class CurrentSession {
  private readonly authenticate: Authenticate;
  private readonly cookie: SessionCookie;

  constructor(authenticate: Authenticate, cookie: SessionCookie) {
    this.authenticate = authenticate;
    this.cookie = cookie;
  }

  require(req: IncomingMessage): Promise<AuthSession> {
    return this.authenticate.execute(this.cookie.read(req));
  }
}
