// Configuração do BFF a partir do ambiente (contracts/env.example). Erros
// citam o nome da variável, nunca o valor.
import { parsePasswordHash, type PasswordHash } from "../infrastructure/auth/scryptPasswordVerifier.ts";

export interface BffConfig {
  port: number;
  fakes: boolean;
  onCloudRun: boolean;
  usersFixture: string;
  bigQuery: { project: string; dataset: string; table: string };
  passwordHash: PasswordHash;
  cookieSecure: boolean;
  allowedOrigins: string[];
  agentUrl: string;
  agentApp: string;
  agentUseOidc: boolean;
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

  return {
    port,
    fakes,
    onCloudRun,
    usersFixture: env.USERS_FIXTURE || defaults.usersFixture,
    bigQuery: { project, dataset: env.BQ_DATASET_DADOS || "bussola_dados", table: env.BQ_TABLE_USERS || "users" },
    passwordHash,
    cookieSecure: flag(env.AUTH_COOKIE_SECURE, onCloudRun),
    allowedOrigins: origins(env.AUTH_ALLOWED_ORIGINS),
    agentUrl: env.AGENT_URL || "http://localhost:8000",
    agentApp: env.AGENT_APP || "bussola_agent",
    agentUseOidc,
    staticDir: env.STATIC_DIR || undefined,
  };
}
