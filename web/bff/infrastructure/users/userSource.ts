import type { UserAccount } from "../../domain/userAccount.ts";

/** Origem crua das contas (fixture ou BigQuery), lida inteira a cada carga. */
export interface UserSource {
  loadAll(): Promise<UserAccount[]>;
}
