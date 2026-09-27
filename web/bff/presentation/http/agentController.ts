// Proxy estreito para o ADK: criar e ler sessão e rodar um turno. O
// `id_usuario` vem da conta do cookie; do `/run_sse` só passa o texto.
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { exceptionName, type Logger } from "../../application/ports/logger.ts";
import type { GetAgentSession } from "../../application/useCases/getAgentSession.ts";
import type { SendMessage } from "../../application/useCases/sendMessage.ts";
import type { StartAgentSession } from "../../application/useCases/startAgentSession.ts";
import type { CurrentSession } from "./currentSession.ts";
import { notFound } from "./httpErrors.ts";
import { decodeSegment, parseRunRequest, readJson } from "./requests.ts";
import { sendJson } from "./responses.ts";
import { requireAllowedOrigin } from "./security.ts";

const SESSION_BODY_LIMIT = 1024;
const RUN_BODY_LIMIT = 16 * 1024;

export interface AgentControllerDeps {
  startSession: StartAgentSession;
  getSession: GetAgentSession;
  sendMessage: SendMessage;
  currentSession: CurrentSession;
  agentApp: string;
  allowedOrigins: readonly string[];
  logger: Logger;
}

export class AgentController {
  private readonly deps: AgentControllerDeps;

  constructor(deps: AgentControllerDeps) {
    this.deps = deps;
  }

  async createSession(req: IncomingMessage, res: ServerResponse, app: string): Promise<void> {
    const { startSession, currentSession, allowedOrigins } = this.deps;
    requireAllowedOrigin(req, allowedOrigins);
    const session = await currentSession.require(req);
    this.requireApp(app);
    // O corpo só precisa ser JSON e é descartado: o state inicial vem da conta.
    await readJson(req, SESSION_BODY_LIMIT);
    sendJson(res, 200, await startSession.execute(session));
  }

  async readSession(req: IncomingMessage, res: ServerResponse, app: string, id: string): Promise<void> {
    const session = await this.deps.currentSession.require(req);
    this.requireApp(app);
    sendJson(res, 200, await this.deps.getSession.execute(session, decodeSegment(id)));
  }

  async run(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const { sendMessage, currentSession, allowedOrigins, logger } = this.deps;
    requireAllowedOrigin(req, allowedOrigins);
    const session = await currentSession.require(req);
    const input = parseRunRequest(await readJson(req, RUN_BODY_LIMIT));

    const abort = new AbortController();
    res.on("close", () => abort.abort());
    const started = Date.now();
    let events: AsyncIterable<Uint8Array>;
    try {
      events = await sendMessage.execute(session, input, abort.signal);
    } catch (error) {
      if (abort.signal.aborted) return;
      throw error;
    }
    res.writeHead(200, {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Accel-Buffering": "no",
    });
    try {
      await pipeline(Readable.from(events, { objectMode: false }), res);
      logger.info("turno concluído", { evento: "turno", session_id: input.sessionId, latencia_ms: Date.now() - started });
    } catch (error) {
      if (!abort.signal.aborted) {
        logger.warn("turno interrompido", {
          evento: "turno_interrompido",
          session_id: input.sessionId,
          excecao: exceptionName(error),
        });
      }
    }
  }

  private requireApp(app: string): void {
    if (decodeSegment(app) !== this.deps.agentApp) throw notFound();
  }
}
