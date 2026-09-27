// Login simulado: qualquer persona da tabela de users entra com a senha padrão
// de teste. Login inexistente e senha errada dão a mesma resposta, no mesmo
// tempo, e contam para o limite de tentativas.
import type { AuthSession } from "../../domain/authSession.ts";
import { normalizeLogin, toPublicPersona, type PublicPersona, type UserAccount } from "../../domain/userAccount.ts";
import { InvalidCredentials, TooManyAttempts } from "../errors.ts";
import type { Logger } from "../ports/logger.ts";
import type { LoginRateLimiter } from "../ports/loginRateLimiter.ts";
import type { PasswordVerifier } from "../ports/passwordVerifier.ts";
import type { SessionRepository } from "../ports/sessionRepository.ts";
import type { UserRepository } from "../ports/userRepository.ts";

export interface LoginInput {
  login: unknown;
  password: unknown;
  /** Token do cookie atual, revogado quando o login dá certo. */
  previousToken?: string;
}

export interface LoginResult {
  session: AuthSession;
  persona: PublicPersona;
}

export interface LoginDeps {
  users: UserRepository;
  verifier: PasswordVerifier;
  sessions: SessionRepository;
  rateLimiter: LoginRateLimiter;
  logger: Logger;
  /** Verificações de senha simultâneas (scrypt usa CPU e memória). */
  maxConcurrent?: number;
}

const GLOBAL_KEY = "global:login";

export class Login {
  private readonly deps: Required<LoginDeps>;
  private inFlight = 0;

  constructor(deps: LoginDeps) {
    this.deps = { maxConcurrent: 8, ...deps };
  }

  async execute(input: LoginInput): Promise<LoginResult> {
    const { users, verifier, sessions, rateLimiter, logger, maxConcurrent } = this.deps;
    const login = normalizeLogin(input.login);
    const keys = [`login:${login ?? "?"}`, GLOBAL_KEY];
    if (rateLimiter.isBlocked(keys) || this.inFlight >= maxConcurrent) throw new TooManyAttempts();

    this.inFlight += 1;
    let checked: [UserAccount | null, boolean];
    try {
      // Busca e scrypt sempre, com ou sem conta: o tempo não revela logins.
      checked = await Promise.all([users.findByLogin(login ?? ""), verifier.verify(input.password)]);
    } finally {
      this.inFlight -= 1;
    }
    const [account, passwordOk] = checked;
    if (!account || !passwordOk) {
      rateLimiter.recordFailure(keys);
      logger.warn("login recusado", { evento: "login_recusado", erro_codigo: "CREDENCIAIS_INVALIDAS" });
      throw new InvalidCredentials();
    }

    rateLimiter.reset(keys[0]);
    if (input.previousToken) await sessions.revoke(input.previousToken);
    const session = await sessions.create(account);
    logger.info("login", { evento: "login", id_usuario: account.idUsuario });
    return { session, persona: toPublicPersona(account) };
  }
}
