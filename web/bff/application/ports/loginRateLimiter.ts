/**
 * Limite de falhas de login por chave com prefixo (`login:<login>`,
 * `global:login`). A senha é a mesma para todas as personas, então o limite
 * global importa tanto quanto o por login.
 */
export interface LoginRateLimiter {
  isBlocked(keys: readonly string[]): boolean;
  recordFailure(keys: readonly string[]): void;
  reset(key: string): void;
}
