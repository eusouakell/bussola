// Cabeçalhos de segurança e checagem de origem (CSRF) das escritas.
import type { IncomingMessage } from "node:http";
import { HttpError } from "./httpErrors.ts";

const BASE_HEADERS: Readonly<Record<string, string>> = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Resource-Policy": "same-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Content-Security-Policy": [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
  ].join("; "),
};

export function securityHeaders(secure: boolean): Readonly<Record<string, string>> {
  return secure ? { ...BASE_HEADERS, "Strict-Transport-Security": "max-age=31536000; includeSubDomains" } : BASE_HEADERS;
}

function ownOrigin(req: IncomingMessage): string | null {
  const host = req.headers.host;
  if (!host) return null;
  const forwarded = req.headers["x-forwarded-proto"];
  const proto = (Array.isArray(forwarded) ? forwarded[0] : forwarded)?.split(",", 1)[0].trim();
  return `${proto === "https" ? "https" : "http"}://${host}`;
}

/** Toda escrita exige `Origin` igual à do próprio serviço ou a uma da lista. */
export function requireAllowedOrigin(req: IncomingMessage, allowedOrigins: readonly string[]): void {
  const origin = req.headers.origin;
  if (!origin || (origin !== ownOrigin(req) && !allowedOrigins.includes(origin))) {
    throw new HttpError(403, "ORIGEM_RECUSADA", "Origem não permitida.");
  }
}
