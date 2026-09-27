import type { AuthSession } from "../../domain/authSession.ts";
import type { UserAccount } from "../../domain/userAccount.ts";

/** Guarda as sessões de login. A expiração é regra do caso de uso `Authenticate`. */
export interface SessionRepository {
  /** Cria a sessão com um token opaco novo. */
  create(account: UserAccount): Promise<AuthSession>;
  find(token: string): Promise<AuthSession | null>;
  revoke(token: string): Promise<void>;
}
