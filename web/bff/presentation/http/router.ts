// Roteamento do BFF: API (`/auth/*`, `/apps/*`, `/run_sse`), health check e,
// no resto, os arquivos do front com fallback de SPA. Toda resposta leva os
// cabeçalhos de segurança; toda falha sai no envelope de erro.
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Logger } from "../../application/ports/logger.ts";
import type { AgentController } from "./agentController.ts";
import type { AuthController } from "./authController.ts";
import { notFound, toHttpError } from "./httpErrors.ts";
import { hasUnreadBody } from "./requests.ts";
import { sendError, sendJson } from "./responses.ts";
import { securityHeaders } from "./security.ts";
import { serveStatic } from "./staticFiles.ts";

const SESSIONS_PATH = /^\/apps\/([^/]+)\/users\/[^/]+\/sessions$/;
const SESSION_PATH = /^\/apps\/([^/]+)\/users\/[^/]+\/sessions\/([^/]+)$/;

export interface RouterDeps {
  auth: AuthController;
  agent: AgentController;
  logger: Logger;
  secure: boolean;
  staticDir?: string;
}

export type RequestHandler = (req: IncomingMessage, res: ServerResponse) => void;

function isApi(pathname: string): boolean {
  return pathname.startsWith("/auth/") || pathname.startsWith("/apps/") || pathname === "/run_sse";
}

export function createRequestHandler(deps: RouterDeps): RequestHandler {
  const { auth, agent, logger, staticDir } = deps;
  const headers = securityHeaders(deps.secure);

  async function route(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const method = req.method ?? "GET";
    const { pathname } = new URL(req.url ?? "/", "http://bff.invalid");

    if (pathname === "/healthz" && method === "GET") return sendJson(res, 200, { status: "ok" });
    if (pathname === "/auth/personas" && method === "GET") return auth.personas(req, res);
    if (pathname === "/auth/login" && method === "POST") return auth.login(req, res);
    if (pathname === "/auth/logout" && method === "POST") return auth.logout(req, res);
    if (pathname === "/auth/me" && method === "GET") return auth.me(req, res);
    if (pathname === "/run_sse" && method === "POST") return agent.run(req, res);

    const sessions = SESSIONS_PATH.exec(pathname);
    if (sessions && method === "POST") return agent.createSession(req, res, sessions[1]);
    const session = SESSION_PATH.exec(pathname);
    if (session && method === "GET") return agent.readSession(req, res, session[1], session[2]);

    if (!isApi(pathname) && (method === "GET" || method === "HEAD") && staticDir) {
      if (await serveStatic(staticDir, pathname, res, method === "HEAD")) return;
    }
    throw notFound();
  }

  return (req, res) => {
    for (const [name, value] of Object.entries(headers)) res.setHeader(name, value);
    route(req, res).catch((error: unknown) => {
      const failure = toHttpError(error, logger);
      if (res.headersSent) {
        res.destroy();
        return;
      }
      // Corpo não lido (grande demais, tipo errado): fecha a conexão depois de responder.
      if (hasUnreadBody(req)) {
        res.setHeader("Connection", "close");
        res.once("finish", () => req.destroy());
      }
      sendError(res, failure);
    });
  };
}
