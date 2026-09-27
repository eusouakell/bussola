// @vitest-environment node
import { describe, expect, it } from "vitest";
import { ManualClock } from "../../test/helpers.ts";
import { InMemoryLoginRateLimiter } from "./inMemoryLoginRateLimiter.ts";

function limiter(clock: ManualClock) {
  return new InMemoryLoginRateLimiter(
    { login: { maxFailures: 3, windowMs: 1000 }, global: { maxFailures: 5, windowMs: 1000 } },
    clock.now,
  );
}

describe("InMemoryLoginRateLimiter", () => {
  it("bloqueia o login depois do máximo de falhas na janela", () => {
    const clock = new ManualClock();
    const limits = limiter(clock);
    const keys = ["login:fernando", "global:login"];
    for (let i = 0; i < 3; i += 1) {
      expect(limits.isBlocked(keys)).toBe(false);
      limits.recordFailure(keys);
    }
    expect(limits.isBlocked(keys)).toBe(true);
    expect(limits.isBlocked(["login:outra", "global:login"])).toBe(false);
  });

  it("libera quando as falhas saem da janela", () => {
    const clock = new ManualClock();
    const limits = limiter(clock);
    const keys = ["login:fernando"];
    for (let i = 0; i < 3; i += 1) limits.recordFailure(keys);
    clock.advance(1001);
    expect(limits.isBlocked(keys)).toBe(false);
  });

  it("o limite global pega tentativas espalhadas por logins", () => {
    const clock = new ManualClock();
    const limits = limiter(clock);
    for (let i = 0; i < 5; i += 1) limits.recordFailure([`login:l${i}x`, "global:login"]);
    expect(limits.isBlocked(["login:nova", "global:login"])).toBe(true);
  });

  it("reset limpa só a chave pedida", () => {
    const clock = new ManualClock();
    const limits = limiter(clock);
    const keys = ["login:fernando", "global:login"];
    for (let i = 0; i < 3; i += 1) limits.recordFailure(keys);
    limits.reset("login:fernando");
    expect(limits.isBlocked(["login:fernando"])).toBe(false);
  });

  it("chave sem limite configurado é erro de programação", () => {
    expect(() => limiter(new ManualClock()).isBlocked(["ip:1.2.3.4"])).toThrow("sem limite");
  });
});
