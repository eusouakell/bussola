// @vitest-environment node
import { describe, expect, it } from "vitest";
import { account } from "../test/helpers.ts";
import { AuthSession } from "./authSession.ts";

const policy = { idleTtlMs: 1000, absoluteTtlMs: 5000, maxAgentSessions: 2 };

describe("AuthSession", () => {
  it("expira por inatividade; o uso renova", () => {
    const session = new AuthSession("t", account("fernando"), 0);
    expect(session.isExpired(policy, 1000)).toBe(false);
    expect(session.isExpired(policy, 1001)).toBe(true);
    session.touch(900);
    expect(session.isExpired(policy, 1800)).toBe(false);
  });

  it("expira pelo prazo absoluto mesmo em uso", () => {
    const session = new AuthSession("t", account("fernando"), 0);
    for (let now = 900; now <= 4500; now += 900) session.touch(now);
    expect(session.isExpired(policy, 5000)).toBe(false);
    expect(session.isExpired(policy, 5001)).toBe(true);
  });

  it("só é dona das sessões do agente que registrou, até o limite", () => {
    const session = new AuthSession("t", account("fernando"), 0);
    expect(session.ownsAgentSession("s1")).toBe(false);
    session.bindAgentSession("s1", policy);
    session.bindAgentSession("s2", policy);
    session.bindAgentSession("s3", policy);
    expect(session.ownsAgentSession("s1")).toBe(false);
    expect(session.ownsAgentSession("s2")).toBe(true);
    expect(session.ownsAgentSession("s3")).toBe(true);
    expect(session.ownsAgentSession(undefined)).toBe(false);
    expect(session.ownsAgentSession(["s2"])).toBe(false);
  });
});
