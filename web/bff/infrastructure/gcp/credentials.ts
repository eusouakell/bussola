// Credenciais GCP sem SDK (Strategy): no Cloud Run, o metadata server da
// instância; local, o ADC do gcloud. Tokens ficam só em memória e nunca vão
// para log.
import { execFile } from "node:child_process";

export interface AccessTokenProvider {
  accessToken(): Promise<string>;
}

export interface IdTokenProvider {
  idToken(audience: string): Promise<string>;
}

type Fetch = typeof fetch;

const METADATA = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default";
const REFRESH_MARGIN_MS = 60_000;
// ID tokens do metadata server valem 1 h; renova com folga.
const ID_TOKEN_TTL_MS = 50 * 60_000;

interface Cached {
  value: string;
  expiresAt: number;
}

export class CredentialsError extends Error {
  constructor(reason: string) {
    super(`credenciais GCP indisponíveis: ${reason}`);
    this.name = "CredentialsError";
  }
}

export class MetadataServerCredentials implements AccessTokenProvider, IdTokenProvider {
  private readonly fetch: Fetch;
  private readonly now: () => number;
  private access: Cached | null = null;
  private readonly identities = new Map<string, Cached>();

  constructor(options: { fetch?: Fetch; now?: () => number } = {}) {
    this.fetch = options.fetch ?? fetch;
    this.now = options.now ?? Date.now;
  }

  async accessToken(): Promise<string> {
    if (this.access && this.access.expiresAt > this.now()) return this.access.value;
    const body = (await this.get(`${METADATA}/token`).then((r) => r.json())) as {
      access_token?: unknown;
      expires_in?: unknown;
    };
    if (typeof body.access_token !== "string" || typeof body.expires_in !== "number") {
      throw new CredentialsError("resposta de token inválida");
    }
    this.access = { value: body.access_token, expiresAt: this.now() + body.expires_in * 1000 - REFRESH_MARGIN_MS };
    return this.access.value;
  }

  async idToken(audience: string): Promise<string> {
    const cached = this.identities.get(audience);
    if (cached && cached.expiresAt > this.now()) return cached.value;
    const query = new URLSearchParams({ audience, format: "full" });
    const value = (await this.get(`${METADATA}/identity?${query}`).then((r) => r.text())).trim();
    if (!value) throw new CredentialsError("ID token vazio");
    this.identities.set(audience, { value, expiresAt: this.now() + ID_TOKEN_TTL_MS });
    return value;
  }

  private async get(url: string): Promise<Response> {
    let response: Response;
    try {
      response = await this.fetch(url, { headers: { "Metadata-Flavor": "Google" }, signal: AbortSignal.timeout(5000) });
    } catch {
      throw new CredentialsError("metadata server fora do ar");
    }
    if (!response.ok) throw new CredentialsError(`metadata server respondeu ${response.status}`);
    return response;
  }
}

export type RunCommand = (file: string, args: string[]) => Promise<string>;

const runCommand: RunCommand = (file, args) =>
  new Promise((resolve, reject) => {
    execFile(file, args, { timeout: 15_000 }, (error, stdout) => (error ? reject(error) : resolve(stdout)));
  });

/** Desenvolvimento local: `gcloud auth application-default print-access-token`. */
export class GcloudAdcCredentials implements AccessTokenProvider {
  private readonly run: RunCommand;
  private readonly now: () => number;
  private access: Cached | null = null;

  constructor(options: { run?: RunCommand; now?: () => number } = {}) {
    this.run = options.run ?? runCommand;
    this.now = options.now ?? Date.now;
  }

  async accessToken(): Promise<string> {
    if (this.access && this.access.expiresAt > this.now()) return this.access.value;
    let value: string;
    try {
      value = (await this.run("gcloud", ["auth", "application-default", "print-access-token"])).trim();
    } catch {
      throw new CredentialsError("rode `gcloud auth application-default login`");
    }
    if (!value) throw new CredentialsError("token vazio do gcloud");
    // O gcloud não informa a validade; 5 min fica bem abaixo da hora do token.
    this.access = { value, expiresAt: this.now() + 5 * 60_000 };
    return value;
  }
}
