// Repositório de contas com cache em memória sobre uma `UserSource`
// (fixture em modo fake, BigQuery em produção).
import type { UserRepository } from "../../application/ports/userRepository.ts";
import type { UserAccount } from "../../domain/userAccount.ts";
import type { UserSource } from "./userSource.ts";

export interface CachedUserRepositoryOptions {
  ttlMs: number;
  now?: () => number;
}

export class CachedUserRepository implements UserRepository {
  private readonly source: UserSource;
  private readonly ttlMs: number;
  private readonly now: () => number;
  private cache: Map<string, UserAccount> | null = null;
  private loadedAt = 0;
  private pending: Promise<Map<string, UserAccount>> | null = null;

  constructor(source: UserSource, options: CachedUserRepositoryOptions) {
    this.source = source;
    this.ttlMs = options.ttlMs;
    this.now = options.now ?? Date.now;
  }

  async findByLogin(login: string): Promise<UserAccount | null> {
    return (await this.accounts()).get(login) ?? null;
  }

  async listFeatured(): Promise<UserAccount[]> {
    return [...(await this.accounts()).values()].filter((account) => account.featured);
  }

  private async accounts(): Promise<Map<string, UserAccount>> {
    if (this.cache && this.now() - this.loadedAt < this.ttlMs) return this.cache;
    this.pending ??= this.reload().finally(() => {
      this.pending = null;
    });
    try {
      return await this.pending;
    } catch (error) {
      // Origem fora do ar: segue com a última carga boa, se houver.
      if (this.cache) return this.cache;
      throw error;
    }
  }

  private async reload(): Promise<Map<string, UserAccount>> {
    const accounts = await this.source.loadAll();
    const byLogin = new Map<string, UserAccount>();
    for (const account of accounts) {
      if (byLogin.has(account.login)) throw new Error("login duplicado na origem de users");
      byLogin.set(account.login, account);
    }
    this.cache = byLogin;
    this.loadedAt = this.now();
    return byLogin;
  }
}
