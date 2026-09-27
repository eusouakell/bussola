// Rotas `/auth/*`: lista de personas, login simulado, logout e sessão atual.
import type { IncomingMessage, ServerResponse } from "node:http";
import type { ListPersonas } from "../../application/useCases/listPersonas.ts";
import type { Login } from "../../application/useCases/login.ts";
import type { Logout } from "../../application/useCases/logout.ts";
import { toPublicPersona } from "../../domain/userAccount.ts";
import type { SessionCookie } from "./cookies.ts";
import type { CurrentSession } from "./currentSession.ts";
import { parseLoginRequest, readJson } from "./requests.ts";
import { sendJson } from "./responses.ts";
import { requireAllowedOrigin } from "./security.ts";

const LOGIN_BODY_LIMIT = 1024;

export interface AuthControllerDeps {
  listPersonas: ListPersonas;
  login: Login;
  logout: Logout;
  currentSession: CurrentSession;
  cookie: SessionCookie;
  allowedOrigins: readonly string[];
}

export class AuthController {
  private readonly deps: AuthControllerDeps;

  constructor(deps: AuthControllerDeps) {
    this.deps = deps;
  }

  async personas(_req: IncomingMessage, res: ServerResponse): Promise<void> {
    sendJson(res, 200, { personas: await this.deps.listPersonas.execute() });
  }

  async login(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const { login, cookie, allowedOrigins } = this.deps;
    requireAllowedOrigin(req, allowedOrigins);
    const credentials = parseLoginRequest(await readJson(req, LOGIN_BODY_LIMIT));
    const { session, persona } = await login.execute({ ...credentials, previousToken: cookie.read(req) });
    sendJson(res, 200, { usuario: persona }, { "Set-Cookie": cookie.issue(session.token) });
  }

  async logout(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const { logout, cookie, allowedOrigins } = this.deps;
    requireAllowedOrigin(req, allowedOrigins);
    await logout.execute(cookie.read(req));
    res.writeHead(204, { "Set-Cookie": cookie.clear(), "Cache-Control": "no-store" });
    res.end();
  }

  async me(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const session = await this.deps.currentSession.require(req);
    sendJson(res, 200, { usuario: toPublicPersona(session.account) });
  }
}
