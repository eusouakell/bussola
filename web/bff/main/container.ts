// Composition root: único lugar que conhece todas as camadas. Escolhe os
// adapters pela configuração e injeta portas nos casos de uso e estes nos
// controllers.
import { exceptionName, type Logger } from "../application/ports/logger.ts";
import { Authenticate } from "../application/useCases/authenticate.ts";
import { GetAgentSession } from "../application/useCases/getAgentSession.ts";
import { ListPersonas } from "../application/useCases/listPersonas.ts";
import { Login } from "../application/useCases/login.ts";
import { Logout } from "../application/useCases/logout.ts";
import { SendMessage } from "../application/useCases/sendMessage.ts";
import { StartAgentSession } from "../application/useCases/startAgentSession.ts";
import type { SessionPolicy } from "../domain/authSession.ts";
import { HttpAgentGateway } from "../infrastructure/agent/httpAgentGateway.ts";
import { InMemoryLoginRateLimiter } from "../infrastructure/auth/inMemoryLoginRateLimiter.ts";
import { InMemorySessionRepository } from "../infrastructure/auth/inMemorySessionRepository.ts";
import { ScryptPasswordVerifier } from "../infrastructure/auth/scryptPasswordVerifier.ts";
import { GcloudAdcCredentials, MetadataServerCredentials } from "../infrastructure/gcp/credentials.ts";
import { BigQueryUserSource } from "../infrastructure/users/bigQueryUserSource.ts";
import { CachedUserRepository } from "../infrastructure/users/cachedUserRepository.ts";
import { FixtureUserSource } from "../infrastructure/users/fixtureUserSource.ts";
import type { UserSource } from "../infrastructure/users/userSource.ts";
import { AgentController } from "../presentation/http/agentController.ts";
import { AuthController } from "../presentation/http/authController.ts";
import { SessionCookie } from "../presentation/http/cookies.ts";
import { CurrentSession } from "../presentation/http/currentSession.ts";
import { createRequestHandler, type RequestHandler } from "../presentation/http/router.ts";
import type { BffConfig } from "./config.ts";

const MINUTE = 60_000;

export const SESSION_POLICY: SessionPolicy = {
  idleTtlMs: 30 * MINUTE,
  absoluteTtlMs: 8 * 60 * MINUTE,
  maxAgentSessions: 20,
};

export interface Bff {
  handler: RequestHandler;
  /** Carrega as contas já na subida: falha de BigQuery aparece no log cedo. */
  warmUp(): Promise<void>;
}

export function buildContainer(config: BffConfig, logger: Logger): Bff {
  const metadata = config.onCloudRun ? new MetadataServerCredentials() : null;
  const source: UserSource = config.fakes
    ? new FixtureUserSource(config.usersFixture)
    : new BigQueryUserSource({
        ...config.bigQuery,
        credentials: metadata ?? new GcloudAdcCredentials(),
        onInvalidRows: (count) =>
          logger.warn(`${count} linhas inválidas ignoradas em users`, { evento: "users_linhas_invalidas" }),
      });

  const users = new CachedUserRepository(source, { ttlMs: 10 * MINUTE });
  const sessions = new InMemorySessionRepository({ maxSessions: 500, policy: SESSION_POLICY });
  const agent = new HttpAgentGateway({
    baseUrl: config.agentUrl,
    audience: config.agentAudience,
    app: config.agentApp,
    idTokens: config.agentUseOidc && metadata ? metadata : undefined,
  });

  const cookie = new SessionCookie(config.cookieSecure, SESSION_POLICY.absoluteTtlMs / 1000);
  const currentSession = new CurrentSession(new Authenticate({ sessions, policy: SESSION_POLICY }), cookie);

  const auth = new AuthController({
    listPersonas: new ListPersonas(users),
    login: new Login({
      users,
      verifier: new ScryptPasswordVerifier(config.passwordHash),
      sessions,
      rateLimiter: new InMemoryLoginRateLimiter({
        login: { maxFailures: 5, windowMs: 15 * MINUTE },
        global: { maxFailures: 30, windowMs: MINUTE },
      }),
      logger,
    }),
    logout: new Logout(sessions),
    currentSession,
    cookie,
    allowedOrigins: config.allowedOrigins,
  });

  const agentController = new AgentController({
    startSession: new StartAgentSession({ agent, policy: SESSION_POLICY, logger }),
    getSession: new GetAgentSession(agent),
    sendMessage: new SendMessage(agent),
    currentSession,
    agentApp: config.agentApp,
    allowedOrigins: config.allowedOrigins,
    logger,
  });

  return {
    handler: createRequestHandler({
      auth,
      agent: agentController,
      logger,
      secure: config.cookieSecure,
      staticDir: config.staticDir,
    }),
    async warmUp() {
      try {
        await users.listFeatured();
      } catch (error) {
        logger.error("falha ao carregar users", { evento: "users_indisponivel", excecao: exceptionName(error) });
      }
    },
  };
}
