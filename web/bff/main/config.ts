// Configuração do BFF a partir do ambiente (contracts/env.example). Erros
// citam o nome da variável, nunca o valor.
import type { SessionPolicy } from "../domain/authSession.ts";
import { parsePasswordHash, type PasswordHash } from "../infrastructure/auth/scryptPasswordVerifier.ts";
import { sessionCookieName } from "../presentation/http/cookies.ts";

const SEGUNDO = 1000;
const MINUTO = 60 * SEGUNDO;

export interface RateLimit {
  maxFailures: number;
  windowMs: number;
}

export interface BffConfig {
  port: number;
  fakes: boolean;
  onCloudRun: boolean;
  usersFixture: string;
  bigQuery: { project: string; dataset: string; table: string };
  /** TTL do cache de contas em memória. */
  usersCacheTtlMs: number;
  passwordHash: PasswordHash;
  cookieSecure: boolean;
  /** Nome do cookie de sessão; com HTTPS ganha o prefixo `__Host-`. */
  cookieName: string;
  allowedOrigins: string[];
  /** Validade da sessão de login e teto de sessões do agente por login. */
  sessionPolicy: SessionPolicy;
  /** Teto de sessões de login vivas no processo (`max-instances=1`). */
  maxSessions: number;
  /** Tentativas de login por persona e no processo inteiro. */
  rateLimit: { login: RateLimit; global: RateLimit; maxConcurrent: number };
  agentUrl: string;
  agentAudience: string;
  agentApp: string;
  agentUseOidc: boolean;
  /** Timeout das chamadas não-streaming ao agente. */
  agentTimeoutMs: number;
  /** Prazo para as conexões abertas fecharem depois do SIGTERM. */
  shutdownGraceMs: number;
  staticDir?: string;
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

function flag(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value === "") return fallback;
  const normalized = value.trim().toUpperCase();
  if (normalized === "TRUE") return true;
  if (normalized === "FALSE") return false;
  throw new ConfigError("flag booleana deve ser TRUE ou FALSE");
}

function origins(value: string | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const url = URL.canParse(item) ? new URL(item) : null;
      if (!url || url.origin !== item) throw new ConfigError("AUTH_ALLOWED_ORIGINS: use origens (esquema://host[:porta])");
      return item;
    });
}

/** Inteiro positivo de uma variável; ausente ou vazia usa o padrão. */
function positivo(value: string | undefined, fallback: number, nome: string): number {
  if (value === undefined || value.trim() === "") return fallback;
  const n = Number(value);
  if (!Number.isInteger(n) || n <= 0) throw new ConfigError(`${nome} deve ser um inteiro positivo`);
  return n;
}

export function loadConfig(env: NodeJS.ProcessEnv, defaults: { usersFixture: string }): BffConfig {
  const onCloudRun = Boolean(env.K_SERVICE);
  const port = Number(env.PORT ?? 8080);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new ConfigError("PORT inválida");

  let passwordHash: PasswordHash;
  try {
    passwordHash = parsePasswordHash(env.AUTH_PASSWORD_HASH);
  } catch {
    throw new ConfigError("AUTH_PASSWORD_HASH ausente ou inválido (gere com `npm run hash-password`)");
  }

  const agentUseOidc = flag(env.AGENT_USE_OIDC, false);
  if (agentUseOidc && !onCloudRun) throw new ConfigError("AGENT_USE_OIDC=TRUE só funciona no Cloud Run");
  const fakes = flag(env.BUSSOLA_FAKES, true);
  const project = env.GOOGLE_CLOUD_PROJECT ?? "";
  if (!fakes && !project) throw new ConfigError("GOOGLE_CLOUD_PROJECT é obrigatório com BUSSOLA_FAKES=FALSE");

  const agentUrl = env.AGENT_URL || "http://localhost:8000";
  if (!URL.canParse(agentUrl)) throw new ConfigError("AGENT_URL inválida");
  const agentAudience = env.AGENT_AUDIENCE || new URL(agentUrl).origin;
  if (!URL.canParse(agentAudience)) throw new ConfigError("AGENT_AUDIENCE inválida");

  const cookieSecure = flag(env.AUTH_COOKIE_SECURE, onCloudRun);

  return {
    port,
    fakes,
    onCloudRun,
    usersFixture: env.USERS_FIXTURE || defaults.usersFixture,
    bigQuery: { project, dataset: env.BQ_DATASET_DADOS || "bussola_dados", table: env.BQ_TABLE_USERS || "users" },
    usersCacheTtlMs: positivo(env.USERS_CACHE_TTL_MS, 10 * MINUTO, "USERS_CACHE_TTL_MS"),
    passwordHash,
    cookieSecure,
    cookieName: sessionCookieName(cookieSecure, env.AUTH_COOKIE_NAME),
    allowedOrigins: origins(env.AUTH_ALLOWED_ORIGINS),
    sessionPolicy: {
      idleTtlMs: positivo(env.AUTH_SESSION_IDLE_TTL_MS, 30 * MINUTO, "AUTH_SESSION_IDLE_TTL_MS"),
      absoluteTtlMs: positivo(env.AUTH_SESSION_TTL_MS, 8 * 60 * MINUTO, "AUTH_SESSION_TTL_MS"),
    },
    maxSessions: positivo(env.AUTH_MAX_SESSIONS, 500, "AUTH_MAX_SESSIONS"),
    rateLimit: {
      login: {
        maxFailures: positivo(env.AUTH_LOGIN_MAX_FAILURES, 5, "AUTH_LOGIN_MAX_FAILURES"),
        windowMs: positivo(env.AUTH_LOGIN_WINDOW_MS, 15 * MINUTO, "AUTH_LOGIN_WINDOW_MS"),
      },
      global: {
        maxFailures: positivo(env.AUTH_GLOBAL_MAX_FAILURES, 30, "AUTH_GLOBAL_MAX_FAILURES"),
        windowMs: positivo(env.AUTH_GLOBAL_WINDOW_MS, MINUTO, "AUTH_GLOBAL_WINDOW_MS"),
      },
      maxConcurrent: positivo(env.AUTH_LOGIN_MAX_CONCURRENT, 8, "AUTH_LOGIN_MAX_CONCURRENT"),
    },
    agentUrl,
    agentAudience,
    agentApp: env.AGENT_APP || "bussola_agent",
    agentUseOidc,
    agentTimeoutMs: positivo(env.AGENT_TIMEOUT_MS, 15 * SEGUNDO, "AGENT_TIMEOUT_MS"),
    shutdownGraceMs: positivo(env.SHUTDOWN_GRACE_MS, 10 * SEGUNDO, "SHUTDOWN_GRACE_MS"),
    staticDir: env.STATIC_DIR || undefined,
  };
}
