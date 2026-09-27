// @vitest-environment node
import { describe, expect, it } from "vitest";
import { account, ManualClock } from "../../test/helpers.ts";
import { InMemorySessionRepository } from "./inMemorySessionRepository.ts";

const policy = { idleTtlMs: 1000, absoluteTtlMs: 5000, maxAgentSessions: 2 };

function repository(clock = new ManualClock()) {
  return new InMemorySessionRepository({ maxSessions: 3, policy, now: clock.now });
}

describe("InMemorySessionRepository", () => {
  it("cria token opaco de 256 bits e encontra a sessão", async () => {
    const sessions = repository();
    const fernando = account("fernando");
    const session = await sessions.create(fernando);
    expect(session.token).toMatch(/^[\w-]{43}$/);
    expect(session.token).not.toContain("fernando");
    expect((await sessions.find(session.token))?.account).toBe(fernando);
    expect(await sessions.find("outro-token")).toBeNull();
  });

  it("revoga e, cheio, descarta a mais antiga", async () => {
    const sessions = repository();
    const [a, b, c] = await Promise.all(["a1", "b1", "c1"].map((login) => sessions.create(account(login))));
    await sessions.revoke(b.token);
    expect(await sessions.find(b.token)).toBeNull();
    await sessions.create(account("d1"));
    await sessions.create(account("e1"));
    expect(sessions.size).toBe(3);
    expect(await sessions.find(a.token)).toBeNull();
    expect(await sessions.find(c.token)).not.toBeNull();
  });

  it("ao criar, limpa as expiradas antes de descartar ativas", async () => {
    const clock = new ManualClock();
    const sessions = repository(clock);
    const old = await sessions.create(account("a1"));
    clock.advance(900);
    const active = await sessions.create(account("b1"));
    clock.advance(200);
    await sessions.create(account("c1"));
    expect(await sessions.find(old.token)).toBeNull();
    expect(await sessions.find(active.token)).not.toBeNull();
  });
});
