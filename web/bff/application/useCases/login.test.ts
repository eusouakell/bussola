// @vitest-environment node
import { describe, expect, it } from "vitest";
import { account } from "../../test/helpers.ts";
import { FakePasswordVerifier, FakeRateLimiter, FakeSessionRepository, FakeUserRepository, RecordingLogger } from "../../test/fakes.ts";
import { InvalidCredentials, TooManyAttempts } from "../errors.ts";
import { Login } from "./login.ts";

function setup() {
  const fernando = account("fernando");
  const deps = {
    users: new FakeUserRepository([fernando]),
    verifier: new FakePasswordVerifier("senha-de-teste"),
    sessions: new FakeSessionRepository(),
    rateLimiter: new FakeRateLimiter(),
    logger: new RecordingLogger(),
  };
  return { fernando, deps, login: new Login(deps) };
}

describe("Login", () => {
  it("cria sessão e devolve a persona sem id_usuario", async () => {
    const { fernando, deps, login } = setup();
    const { session, persona } = await login.execute({ login: " Fernando ", password: "senha-de-teste" });
    expect(session.account).toBe(fernando);
    expect(persona).not.toHaveProperty("idUsuario");
    expect(persona.login).toBe("fernando");
    expect(deps.rateLimiter.resets).toEqual(["login:fernando"]);
    expect(deps.logger.entries.at(-1)).toMatchObject({ evento: "login", id_usuario: fernando.idUsuario });
  });

  it("login inexistente e senha errada dão o mesmo erro e sempre verificam a senha", async () => {
    const { deps, login } = setup();
    await expect(login.execute({ login: "fernando", password: "errada" })).rejects.toThrow(InvalidCredentials);
    await expect(login.execute({ login: "ninguem", password: "senha-de-teste" })).rejects.toThrow(InvalidCredentials);
    await expect(login.execute({ login: 42, password: "senha-de-teste" })).rejects.toThrow(InvalidCredentials);
    expect(deps.verifier.calls).toBe(3);
    expect(deps.rateLimiter.failures).toEqual([
      ["login:fernando", "global:login"],
      ["login:ninguem", "global:login"],
      ["login:?", "global:login"],
    ]);
    expect(deps.sessions.sessions.size).toBe(0);
  });

  it("não loga login digitado nem senha", async () => {
    const { deps, login } = setup();
    await login.execute({ login: "fernando", password: "errada" }).catch(() => {});
    const logged = JSON.stringify(deps.logger.entries);
    expect(logged).not.toContain("errada");
    expect(logged).not.toContain("fernando");
  });

  it("bloqueado pelo limite não chega a verificar a senha", async () => {
    const { deps, login } = setup();
    deps.rateLimiter.blocked = true;
    await expect(login.execute({ login: "fernando", password: "senha-de-teste" })).rejects.toThrow(TooManyAttempts);
    expect(deps.verifier.calls).toBe(0);
  });

  it("revoga a sessão anterior do navegador", async () => {
    const { deps, login } = setup();
    const first = await login.execute({ login: "fernando", password: "senha-de-teste" });
    const second = await login.execute({ login: "fernando", password: "senha-de-teste", previousToken: first.session.token });
    expect(await deps.sessions.find(first.session.token)).toBeNull();
    expect(await deps.sessions.find(second.session.token)).toBe(second.session);
  });

  it("limita verificações simultâneas", async () => {
    const { deps } = setup();
    let release = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    const slowVerifier = { verify: async () => (await gate, true) };
    const login = new Login({ ...deps, verifier: slowVerifier, maxConcurrent: 1 });
    const first = login.execute({ login: "fernando", password: "x" });
    await expect(login.execute({ login: "fernando", password: "x" })).rejects.toThrow(TooManyAttempts);
    release();
    await expect(first).resolves.toBeDefined();
  });
});
