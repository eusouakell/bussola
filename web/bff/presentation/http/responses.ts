import type { ServerResponse } from "node:http";
import type { HttpError } from "./httpErrors.ts";

export function sendJson(res: ServerResponse, status: number, body: unknown, headers: Record<string, string> = {}): void {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
    "Cache-Control": "no-store",
    ...headers,
  });
  res.end(payload);
}

export function sendError(res: ServerResponse, error: HttpError): void {
  sendJson(res, error.status, { erro: { codigo: error.code, mensagem: error.message } });
}
