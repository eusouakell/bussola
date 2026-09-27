// @vitest-environment node
import { randomBytes } from "node:crypto";
import { describe, expect, it } from "vitest";
import { hashPassword, InvalidPasswordHash, MAX_PASSWORD_LENGTH, parsePasswordHash, ScryptPasswordVerifier } from "./scryptPasswordVerifier.ts";

// Senha gerada a cada execução: nenhuma senha fica no repositório.
const password = randomBytes(12).toString("base64url");

describe("hashPassword / ScryptPasswordVerifier", () => {
  it("gera scrypt$N$r$p$salt$hash com sal aleatório", async () => {
    const [a, b] = await Promise.all([hashPassword(password), hashPassword(password)]);
    expect(a).toMatch(/^scrypt\$16384\$8\$1\$[\w-]{22}\$[\w-]{43}$/);
    expect(a).not.toBe(b);
    expect(a).not.toContain(password);
  });

  it("aceita a senha certa e recusa as outras", async () => {
    const verifier = new ScryptPasswordVerifier(parsePasswordHash(await hashPassword(password)));
    expect(await verifier.verify(password)).toBe(true);
    expect(await verifier.verify(`${password}x`)).toBe(false);
    expect(await verifier.verify(password.toUpperCase())).toBe(false);
  });

  it.each([undefined, null, 123, "", "x".repeat(MAX_PASSWORD_LENGTH + 1), { senha: "x" }])(
    "recusa entrada inválida %#",
    async (value) => {
      const verifier = new ScryptPasswordVerifier(parsePasswordHash(await hashPassword(password)));
      expect(await verifier.verify(value)).toBe(false);
    },
  );

  it("recusa gerar hash de senha vazia", async () => {
    await expect(hashPassword("")).rejects.toThrow();
  });
});

describe("parsePasswordHash", () => {
  it.each([
    undefined,
    "",
    "texto-puro",
    "bcrypt$16384$8$1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaA",
    "scrypt$1024$8$1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaA",
    "scrypt$20000$8$1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaA",
    "scrypt$16384$8$1$c2FsdA$aGFzaGhhc2hoYXNoaGFzaA",
  ])("recusa %j", (encoded) => {
    expect(() => parsePasswordHash(encoded)).toThrow(InvalidPasswordHash);
  });

  it("a mensagem de erro não repete o valor recebido", () => {
    const secretish = "scrypt$1$2$3$valor-que-nao-pode-vazar$x";
    expect(() => parsePasswordHash(secretish)).toThrow(expect.objectContaining({ message: expect.not.stringContaining("vazar") }));
  });
});
