import type { UserAccount } from "../../domain/userAccount.ts";

/** Contas de login simulado (tabela `bussola_dados.users` ou fixture). */
export interface UserRepository {
  findByLogin(login: string): Promise<UserAccount | null>;
  /** Personas sugeridas na tela de login. */
  listFeatured(): Promise<UserAccount[]>;
}
