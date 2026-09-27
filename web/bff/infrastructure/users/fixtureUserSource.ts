// Origem de contas em modo fake: `contracts/fixtures/bussola_dados/users.json`
// (lista JSON com as colunas do DDL). Linha inválida derruba a carga: a
// fixture é versionada e tem de estar certa.
import { readFile } from "node:fs/promises";
import { parseUserAccount, type UserAccount } from "../../domain/userAccount.ts";
import type { UserSource } from "./userSource.ts";

export class FixtureUserSource implements UserSource {
  private readonly path: string;

  constructor(path: string) {
    this.path = path;
  }

  async loadAll(): Promise<UserAccount[]> {
    const rows: unknown = JSON.parse(await readFile(this.path, "utf-8"));
    if (!Array.isArray(rows)) throw new Error("fixture de users deve ser uma lista");
    return rows.map((row) => parseUserAccount(row as Record<string, unknown>));
  }
}
