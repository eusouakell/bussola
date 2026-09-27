// Conta de login simulado: cada linha de `bussola_dados.users` é uma massa de
// dados sintética. O navegador só conhece o `login`; o `idUsuario` fica no
// servidor e vai para o `session.state` do agente.
import { DomainError } from "./errors.ts";

export interface UserAccount {
  login: string;
  idUsuario: string;
  displayName: string;
  summary: string;
  featured: boolean;
}

/** Dados de uma persona que podem ir ao navegador (sem `idUsuario`). */
export interface PublicPersona {
  login: string;
  displayName: string;
  summary: string;
}

export const LOGIN_PATTERN = /^[a-z0-9][a-z0-9-]{1,31}$/;
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export class InvalidUserRow extends DomainError {
  constructor(field: string) {
    super(`linha de users inválida: ${field}`);
  }
}

/** Login normalizado (minúsculas, sem espaços nas pontas) ou `null` se inválido. */
export function normalizeLogin(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const login = raw.trim().toLowerCase();
  return LOGIN_PATTERN.test(login) ? login : null;
}

function text(row: Record<string, unknown>, field: string, maxLength: number): string {
  const value = row[field];
  if (typeof value !== "string" || value.length > maxLength) throw new InvalidUserRow(field);
  return value;
}

/** Converte uma linha da tabela (colunas do DDL, snake_case) em conta validada. */
export function parseUserAccount(row: Record<string, unknown>): UserAccount {
  const login = normalizeLogin(row.login);
  if (!login || login !== row.login) throw new InvalidUserRow("login");
  const idUsuario = text(row, "id_usuario", 36).toLowerCase();
  if (!UUID_V4.test(idUsuario)) throw new InvalidUserRow("id_usuario");
  const displayName = text(row, "display_name", 80).trim();
  if (!displayName) throw new InvalidUserRow("display_name");
  const featured = row.featured;
  if (typeof featured !== "boolean") throw new InvalidUserRow("featured");
  return { login, idUsuario, displayName, summary: text(row, "summary", 280).trim(), featured };
}

export function toPublicPersona(account: UserAccount): PublicPersona {
  return { login: account.login, displayName: account.displayName, summary: account.summary };
}
