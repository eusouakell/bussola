// Senha padrão de teste guardada só como hash scrypt
// (`scrypt$N$r$p$salt$hash`, base64url). O valor em claro nunca fica no
// repositório: o hash vem do Secret Manager (Cloud Run) ou do `.env` local.
import { randomBytes, scrypt, timingSafeEqual, type ScryptOptions } from "node:crypto";
import type { PasswordVerifier } from "../../application/ports/passwordVerifier.ts";

export const MAX_PASSWORD_LENGTH = 128;
const KEY_LENGTH = 32;
const DEFAULT_PARAMS = { N: 16384, r: 8, p: 1 };

export interface PasswordHash {
  N: number;
  r: number;
  p: number;
  salt: Buffer;
  hash: Buffer;
}

export class InvalidPasswordHash extends Error {
  constructor() {
    super("AUTH_PASSWORD_HASH inválido: esperado scrypt$N$r$p$salt$hash");
    this.name = "InvalidPasswordHash";
  }
}

function derive(password: string, salt: Buffer, keyLength: number, options: ScryptOptions): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scrypt(password.normalize("NFKC"), salt, keyLength, { ...options, maxmem: 64 * 1024 * 1024 }, (error, key) =>
      error ? reject(error) : resolve(key),
    );
  });
}

export async function hashPassword(password: string, params = DEFAULT_PARAMS): Promise<string> {
  if (!password || password.length > MAX_PASSWORD_LENGTH) throw new Error("senha vazia ou longa demais");
  const salt = randomBytes(16);
  const hash = await derive(password, salt, KEY_LENGTH, params);
  return ["scrypt", params.N, params.r, params.p, salt.toString("base64url"), hash.toString("base64url")].join("$");
}

export function parsePasswordHash(encoded: string | undefined): PasswordHash {
  const parts = (encoded ?? "").trim().split("$");
  if (parts.length !== 6 || parts[0] !== "scrypt") throw new InvalidPasswordHash();
  const [N, r, p] = parts.slice(1, 4).map(Number);
  const salt = Buffer.from(parts[4], "base64url");
  const hash = Buffer.from(parts[5], "base64url");
  const powerOfTwo = Number.isInteger(N) && N >= 2 ** 14 && N <= 2 ** 20 && (N & (N - 1)) === 0;
  if (!powerOfTwo || !Number.isInteger(r) || r < 1 || r > 32 || !Number.isInteger(p) || p < 1 || p > 16) {
    throw new InvalidPasswordHash();
  }
  if (salt.length < 16 || hash.length < 16) throw new InvalidPasswordHash();
  return { N, r, p, salt, hash };
}

export class ScryptPasswordVerifier implements PasswordVerifier {
  private readonly expected: PasswordHash;

  constructor(expected: PasswordHash) {
    this.expected = expected;
  }

  async verify(password: unknown): Promise<boolean> {
    const valid = typeof password === "string" && password.length > 0 && password.length <= MAX_PASSWORD_LENGTH;
    const { N, r, p, salt, hash } = this.expected;
    const candidate = await derive(valid ? password : "", salt, hash.length, { N, r, p });
    return timingSafeEqual(candidate, hash) && valid;
  }
}
