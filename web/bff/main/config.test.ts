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
      agentApp: "bussola_agent",
      agentUseOidc: false,
    });
  });

  it("no Cloud Run, cookie Secure e OIDC permitido", () => {
    const config = loadConfig(
      { AUTH_PASSWORD_HASH: hash, K_SERVICE: "bussola-bff", AGENT_USE_OIDC: "TRUE", BUSSOLA_FAKES: "FALSE", GOOGLE_CLOUD_PROJECT: "p" },
      defaults,
    );
    expect(config.cookieSecure).toBe(true);
    expect(config.agentUseOidc).toBe(true);
    expect(config.fakes).toBe(false);
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
  ])("recusa %j", (env, message) => {
    expect(() => loadConfig({ AUTH_PASSWORD_HASH: hash, ...env }, defaults)).toThrow(message);
  });
});
