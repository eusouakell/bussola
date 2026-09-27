// @vitest-environment node
import { describe, expect, it } from "vitest";
import { account } from "../test/helpers.ts";
import { AuthSession } from "./authSession.ts";

const policy = { idleTtlMs: 1000, absoluteTtlMs: 5000 };

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
});
