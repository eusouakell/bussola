// Limite de falhas de login em janela deslizante, em memória (o serviço roda
// com uma instância só).
import type { LoginRateLimiter } from "../../application/ports/loginRateLimiter.ts";

export interface RateLimit {
  maxFailures: number;
  windowMs: number;
}

export class InMemoryLoginRateLimiter implements LoginRateLimiter {
  private readonly failures = new Map<string, number[]>();
  private readonly limits: Record<string, RateLimit>;
  private readonly now: () => number;

  /** `limits` por prefixo de chave, por exemplo `{ login: ..., global: ... }`. */
  constructor(limits: Record<string, RateLimit>, now: () => number = Date.now) {
    this.limits = limits;
    this.now = now;
  }

  isBlocked(keys: readonly string[]): boolean {
    return keys.some((key) => this.recent(key).length >= this.limitOf(key).maxFailures);
  }

  recordFailure(keys: readonly string[]): void {
    for (const key of keys) this.failures.set(key, [...this.recent(key), this.now()]);
  }

  reset(key: string): void {
    this.failures.delete(key);
  }

  private recent(key: string): number[] {
    const { windowMs } = this.limitOf(key);
    const since = this.now() - windowMs;
    const recent = (this.failures.get(key) ?? []).filter((at) => at > since);
    if (recent.length) this.failures.set(key, recent);
    else this.failures.delete(key);
    return recent;
  }

  private limitOf(key: string): RateLimit {
    const limit = this.limits[key.split(":", 1)[0]];
    if (!limit) throw new Error(`sem limite configurado para ${key}`);
    return limit;
  }
}
