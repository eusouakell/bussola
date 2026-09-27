// Entrada do BFF: `node bff/main/index.ts` (Node 24, sem build).
import { createServer } from "node:http";
import { resolve } from "node:path";
import { exceptionName } from "../application/ports/logger.ts";
import { jsonLogger } from "../infrastructure/logging/jsonLogger.ts";
import { ConfigError, loadConfig, type BffConfig } from "./config.ts";
import { buildContainer } from "./container.ts";

const DEFAULT_USERS_FIXTURE = resolve(import.meta.dirname, "../../../contracts/fixtures/bussola_dados/users.json");

function main(): void {
  const logger = jsonLogger();
  let config: BffConfig;
  try {
    config = loadConfig(process.env, { usersFixture: DEFAULT_USERS_FIXTURE });
  } catch (error) {
    process.stderr.write(`Configuração inválida: ${error instanceof ConfigError ? error.message : exceptionName(error)}\n`);
    process.exit(1);
  }

  const bff = buildContainer(config, logger);
  const server = createServer(bff.handler);
  server.listen(config.port, () => {
    logger.info(`bussola-bff na porta ${config.port} (fakes=${config.fakes})`, { evento: "inicio" });
    void bff.warmUp();
  });

  process.once("SIGTERM", () => {
    logger.info("encerrando", { evento: "fim" });
    server.close(() => process.exit(0));
    server.closeIdleConnections();
    setTimeout(() => process.exit(0), config.shutdownGraceMs).unref();
  });
}

main();
