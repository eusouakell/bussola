// Leitura e validação dos pedidos. Corpo só em JSON, com limite de tamanho e
// lista fechada de campos: o que não está na lista é recusado, não ignorado.
import type { IncomingMessage } from "node:http";
import { HttpError, invalidRequest } from "./httpErrors.ts";

const LOGIN_KEYS = new Set(["login", "password"]);
const RUN_KEYS = new Set([
  "appName",
  "app_name",
  "userId",
  "user_id",
  "sessionId",
  "session_id",
  "newMessage",
  "new_message",
  "streaming",
]);
const MESSAGE_KEYS = new Set(["role", "parts"]);
const PART_KEYS = new Set(["text"]);
const MAX_SESSION_ID_CHARS = 128;
const MAX_PARTS = 8;

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function onlyKeys(value: Record<string, unknown>, allowed: ReadonlySet<string>): void {
  if (Object.keys(value).some((key) => !allowed.has(key))) throw invalidRequest();
}

export function decodeSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    throw invalidRequest();
  }
}

export function hasUnreadBody(req: IncomingMessage): boolean {
  const hasBody = Number(req.headers["content-length"] ?? 0) > 0 || req.headers["transfer-encoding"] !== undefined;
  return hasBody && !req.readableEnded;
}

export async function readJson(req: IncomingMessage, limit: number): Promise<unknown> {
  const type = (req.headers["content-type"] ?? "").split(";", 1)[0].trim().toLowerCase();
  if (type !== "application/json") throw new HttpError(415, "TIPO_NAO_SUPORTADO", "Envie o pedido em JSON.");
  const tooLarge = () => new HttpError(413, "PEDIDO_GRANDE", "Pedido grande demais.");
  if (Number(req.headers["content-length"] ?? 0) > limit) throw tooLarge();
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req as AsyncIterable<Buffer>) {
    size += chunk.length;
    if (size > limit) throw tooLarge();
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf-8"));
  } catch {
    throw invalidRequest();
  }
}

export interface LoginRequest {
  login: unknown;
  password: unknown;
}

export function parseLoginRequest(body: unknown): LoginRequest {
  if (!isRecord(body)) throw invalidRequest();
  onlyKeys(body, LOGIN_KEYS);
  return { login: body.login, password: body.password };
}

export interface RunRequest {
  sessionId: string;
  text: string;
}

/**
 * Corpo do `/run_sse` no formato do ADK, reduzido ao texto do cliente.
 * `stateDelta`, `state`, anexos e chamadas de função são recusados.
 */
export function parseRunRequest(body: unknown): RunRequest {
  if (!isRecord(body)) throw invalidRequest();
  onlyKeys(body, RUN_KEYS);
  const sessionId = body.sessionId ?? body.session_id;
  const message = body.newMessage ?? body.new_message;
  if (typeof sessionId !== "string" || !sessionId || sessionId.length > MAX_SESSION_ID_CHARS) throw invalidRequest();
  if (body.streaming !== undefined && typeof body.streaming !== "boolean") throw invalidRequest();
  if (!isRecord(message)) throw invalidRequest();
  onlyKeys(message, MESSAGE_KEYS);
  if (message.role !== undefined && message.role !== "user") throw invalidRequest();
  const parts = message.parts;
  if (!Array.isArray(parts) || parts.length < 1 || parts.length > MAX_PARTS) throw invalidRequest();
  const texts = parts.map((part: unknown) => {
    if (!isRecord(part)) throw invalidRequest();
    onlyKeys(part, PART_KEYS);
    if (typeof part.text !== "string") throw invalidRequest();
    return part.text;
  });
  return { sessionId, text: texts.join("\n") };
}
