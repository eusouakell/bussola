// Cookie da sessão de login: HttpOnly, SameSite=Strict e, com HTTPS, o
// prefixo `__Host-` (exige Secure, Path=/ e nenhum Domain).
import type { IncomingMessage } from "node:http";

/** Nome do cookie (config); com HTTPS ganha o prefixo obrigatório `__Host-`. */
export function sessionCookieName(secure: boolean, base = "bussola_session"): string {
  return secure ? `__Host-${base}` : base;
}

export function readCookie(header: string | undefined, name: string): string | undefined {
  for (const part of (header ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index > 0 && part.slice(0, index).trim() === name) return part.slice(index + 1).trim() || undefined;
  }
  return undefined;
}

export function sessionCookie(name: string, token: string, secure: boolean, maxAgeSeconds: number): string {
  const attributes = [`${name}=${token}`, "Path=/", "HttpOnly", "SameSite=Strict", `Max-Age=${maxAgeSeconds}`];
  if (secure) attributes.push("Secure");
  return attributes.join("; ");
}

export function clearedSessionCookie(name: string, secure: boolean): string {
  return sessionCookie(name, "", secure, 0);
}

/** Cookie da sessão com nome e atributos fixados pela configuração. */
export class SessionCookie {
  readonly name: string;
  private readonly secure: boolean;
  private readonly maxAgeSeconds: number;

  constructor(name: string, secure: boolean, maxAgeSeconds: number) {
    this.name = name;
    this.secure = secure;
    this.maxAgeSeconds = maxAgeSeconds;
  }

  read(req: IncomingMessage): string | undefined {
    return readCookie(req.headers.cookie, this.name);
  }

  issue(token: string): string {
    return sessionCookie(this.name, token, this.secure, this.maxAgeSeconds);
  }

  clear(): string {
    return clearedSessionCookie(this.name, this.secure);
  }
}
