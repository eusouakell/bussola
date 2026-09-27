// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import type { UserAccount } from "../../domain/userAccount.ts";
import { account, ManualClock } from "../../test/helpers.ts";
import { CachedUserRepository } from "./cachedUserRepository.ts";
import type { UserSource } from "./userSource.ts";

function sourceOf(...batches: (UserAccount[] | Error)[]): UserSource & { loadAll: ReturnType<typeof vi.fn> } {
  const loadAll = vi.fn(async () => {
    const next = batches.length > 1 ? batches.shift()! : batches[0];
    if (next instanceof Error) throw next;
    return next;
  });
  return { loadAll };
}

describe("CachedUserRepository", () => {
  it("encontra por login e lista só as personas em destaque", async () => {
    const fernando = account("fernando");
    const outra = account("cliente-0a1b2c3d", { featured: false });
    const users = new CachedUserRepository(sourceOf([fernando, outra]), { ttlMs: 1000 });

    expect(await users.findByLogin("fernando")).toBe(fernando);
    expect(await users.findByLogin("ninguem")).toBeNull();
    expect(await users.listFeatured()).toEqual([fernando]);
  });

  it("usa o cache dentro do TTL e recarrega depois", async () => {
    const clock = new ManualClock();
    const source = sourceOf([account("fernando")]);
    const users = new CachedUserRepository(source, { ttlMs: 1000, now: clock.now });

    await users.findByLogin("fernando");
    await users.findByLogin("fernando");
    expect(source.loadAll).toHaveBeenCalledTimes(1);

    clock.advance(1001);
    await users.findByLogin("fernando");
    expect(source.loadAll).toHaveBeenCalledTimes(2);
  });

  it("carga concorrente chama a origem uma vez só", async () => {
    const source = sourceOf([account("fernando")]);
    const users = new CachedUserRepository(source, { ttlMs: 1000 });
    await Promise.all([users.findByLogin("fernando"), users.listFeatured()]);
    expect(source.loadAll).toHaveBeenCalledTimes(1);
  });

  it("com a origem fora do ar, segue com a última carga boa", async () => {
    const clock = new ManualClock();
    const fernando = account("fernando");
    const users = new CachedUserRepository(sourceOf([fernando], new Error("fora")), { ttlMs: 1000, now: clock.now });

    await users.findByLogin("fernando");
    clock.advance(1001);
    expect(await users.findByLogin("fernando")).toBe(fernando);
  });

  it("sem carga boa, propaga a falha", async () => {
    const users = new CachedUserRepository(sourceOf(new Error("fora")), { ttlMs: 1000 });
    await expect(users.findByLogin("fernando")).rejects.toThrow("fora");
  });

  it("recusa login duplicado na origem", async () => {
    const users = new CachedUserRepository(sourceOf([account("fernando"), account("fernando")]), { ttlMs: 1000 });
    await expect(users.listFeatured()).rejects.toThrow("duplicado");
  });
});
