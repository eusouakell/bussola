// @vitest-environment node
import { describe, expect, it } from "vitest";
import { FakeSessionRepository } from "../../test/fakes.ts";
import { account, ManualClock } from "../../test/helpers.ts";
import { NotAuthenticated } from "../errors.ts";
import { Authenticate } from "./authenticate.ts";

const policy = { idleTtlMs: 1000, absoluteTtlMs: 5000 };

describe("Authenticate", () => {
  it("resolve o token e renova a inatividade", async () => {
    const clock = new ManualClock();
    const sessions = new FakeSessionRepository(clock.now);
    const authenticate = new Authenticate({ sessions, policy, now: clock.now });
    const session = await sessions.create(account("fernando"));
    clock.advance(900);
    await expect(authenticate.execute(session.token)).resolves.toBe(session);
    clock.advance(900);
    await expect(authenticate.execute(session.token)).resolves.toBe(session);
  });

  it("sem token, token desconhecido ou expirado: NotAuthenticated, e a expirada é revogada", async () => {
    const clock = new ManualClock();
    const sessions = new FakeSessionRepository(clock.now);
    const authenticate = new Authenticate({ sessions, policy, now: clock.now });
    const session = await sessions.create(account("fernando"));
    await expect(authenticate.execute(undefined)).rejects.toThrow(NotAuthenticated);
    await expect(authenticate.execute("outro")).rejects.toThrow(NotAuthenticated);
    clock.advance(1001);
    await expect(authenticate.execute(session.token)).rejects.toThrow(NotAuthenticated);
    expect(sessions.sessions.size).toBe(0);
  });
});
