// @vitest-environment node
import { randomBytes } from "node:crypto";
import { beforeAll, describe, expect, it } from "vitest";
import { ConfigError, loadConfig } from "./config.ts";
import { hashPassword } from "../infrastructure/auth/scryptPasswordVerifier.ts";

let hash: string;
beforeAll(async () => {
  hash = await hashPassword(randomBytes(12).toString("base64url"));
});

const defaults = { usersFixture: "/repo/contracts/fixtures/bussola_dados/users.json" };

describe("loadConfig", () => {
  it("padrões locais: fakes, cookie sem Secure, agente em localhost:8000", () => {
    const config = loadConfig({ AUTH_PASSWORD_HASH: hash }, defaults);
    expect(config).toMatchObject({
      port: 8080,
      fakes: true,
      onCloudRun: false,
      usersFixture: defaults.usersFixture,
      bigQuery: { dataset: "bussola_dados", table: "users" },
      cookieSecure: false,
      allowedOrigins: [],
      agentUrl: "http://localhost:8000",
      agentAudience: "http://localhost:8000",
      agentApp: "bussola_agent",
      agentUseOidc: false,
      cookieName: "bussola_session",
      usersCacheTtlMs: 600_000,
      sessionPolicy: { idleTtlMs: 1_800_000, absoluteTtlMs: 28_800_000 },
      maxSessions: 500,
      rateLimit: {
        login: { maxFailures: 5, windowMs: 900_000 },
        global: { maxFailures: 30, windowMs: 60_000 },
        maxConcurrent: 8,
      },
      agentTimeoutMs: 15_000,
      shutdownGraceMs: 10_000,
    });
  });

  it("TTLs, limites e nome de cookie vêm do ambiente", () => {
    const config = loadConfig(
      {
        AUTH_PASSWORD_HASH: hash,
        AUTH_COOKIE_NAME: "demo_session",
        AUTH_SESSION_IDLE_TTL_MS: "60000",
        AUTH_SESSION_TTL_MS: "120000",
        AUTH_MAX_SESSIONS: "10",
        AUTH_LOGIN_MAX_FAILURES: "2",
        AGENT_TIMEOUT_MS: "1000",
      },
      defaults,
    );
    expect(config).toMatchObject({
      cookieName: "demo_session",
      sessionPolicy: { idleTtlMs: 60_000, absoluteTtlMs: 120_000 },
      maxSessions: 10,
      agentTimeoutMs: 1000,
    });
    expect(config.rateLimit.login.maxFailures).toBe(2);
  });

  it("no Cloud Run, cookie Secure e OIDC permitido", () => {
    const config = loadConfig(
      { AUTH_PASSWORD_HASH: hash, K_SERVICE: "bussola-bff", AGENT_USE_OIDC: "TRUE", BUSSOLA_FAKES: "FALSE", GOOGLE_CLOUD_PROJECT: "p" },
      defaults,
    );
    expect(config.cookieSecure).toBe(true);
    expect(config.cookieName).toBe("__Host-bussola_session");
    expect(config.agentUseOidc).toBe(true);
    expect(config.fakes).toBe(false);
  });

  it("audience do agente: origem de AGENT_URL, ou AGENT_AUDIENCE para URL de tag", () => {
    const tag = "https://main---bussola-agent.example.run.app";
    expect(loadConfig({ AUTH_PASSWORD_HASH: hash, AGENT_URL: `${tag}/` }, defaults).agentAudience).toBe(tag);
    const config = loadConfig(
      { AUTH_PASSWORD_HASH: hash, AGENT_URL: tag, AGENT_AUDIENCE: "https://bussola-agent.example.run.app" },
      defaults,
    );
    expect(config).toMatchObject({ agentUrl: tag, agentAudience: "https://bussola-agent.example.run.app" });
  });

  it("sem AUTH_PASSWORD_HASH, falha sem citar valores", () => {
    expect(() => loadConfig({}, defaults)).toThrow(ConfigError);
    expect(() => loadConfig({ AUTH_PASSWORD_HASH: "senha-em-claro" }, defaults)).toThrow(
      expect.objectContaining({ message: expect.not.stringContaining("senha-em-claro") }),
    );
  });

  it.each([
    [{ AGENT_USE_OIDC: "TRUE" }, "só funciona no Cloud Run"],
    [{ BUSSOLA_FAKES: "FALSE" }, "GOOGLE_CLOUD_PROJECT"],
    [{ AUTH_ALLOWED_ORIGINS: "http://localhost:5173/caminho" }, "AUTH_ALLOWED_ORIGINS"],
    [{ AUTH_COOKIE_SECURE: "sim" }, "TRUE ou FALSE"],
    [{ PORT: "0" }, "PORT"],
    [{ AGENT_URL: "bussola-agent" }, "AGENT_URL"],
    [{ AGENT_AUDIENCE: "bussola-agent" }, "AGENT_AUDIENCE"],
    [{ AUTH_SESSION_TTL_MS: "0" }, "AUTH_SESSION_TTL_MS"],
    [{ AUTH_LOGIN_MAX_FAILURES: "-1" }, "AUTH_LOGIN_MAX_FAILURES"],
    [{ AGENT_TIMEOUT_MS: "muito" }, "AGENT_TIMEOUT_MS"],
  ])("recusa %j", (env, message) => {
    expect(() => loadConfig({ AUTH_PASSWORD_HASH: hash, ...env }, defaults)).toThrow(message);
  });
});
