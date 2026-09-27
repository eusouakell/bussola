// @vitest-environment node
import { describe, expect, it } from "vitest";
import { userRow } from "../test/helpers.ts";
import { InvalidUserRow, normalizeLogin, parseUserAccount, toPublicPersona } from "./userAccount.ts";

describe("normalizeLogin", () => {
  it.each([
    ["fernando", "fernando"],
    ["  Fernando ", "fernando"],
    ["cliente-0a1b2c3d", "cliente-0a1b2c3d"],
  ])("aceita %j", (raw, expected) => {
    expect(normalizeLogin(raw)).toBe(expected);
  });

  it.each([undefined, null, 42, "", "a", "-inicio", "com espaço", "x".repeat(33), "ação", "a/b", "a'--"])(
    "recusa %j",
    (raw) => {
      expect(normalizeLogin(raw)).toBeNull();
    },
  );
});

describe("parseUserAccount", () => {
  it("converte a linha do DDL em conta", () => {
    const row = userRow("fernando", { featured: false });
    expect(parseUserAccount(row)).toEqual({
      login: "fernando",
      idUsuario: row.id_usuario,
      displayName: "Persona fernando",
      summary: "Massa de dados sintética.",
      featured: false,
    });
  });

  it.each([
    ["login fora do padrão", { login: "Fernando" }],
    ["id que não é UUID v4", { id_usuario: "36a21505-d6d4-12d3-b319-d51a133c7269" }],
    ["id ausente", { id_usuario: undefined }],
    ["nome vazio", { display_name: "  " }],
    ["featured como texto", { featured: "true" }],
    ["resumo longo demais", { summary: "x".repeat(281) }],
  ])("recusa %s", (_caso, overrides) => {
    expect(() => parseUserAccount(userRow("fernando", overrides))).toThrow(InvalidUserRow);
  });

  it("a persona pública não leva o id_usuario", () => {
    const persona = toPublicPersona(parseUserAccount(userRow("fernando")));
    expect(persona).toEqual({ login: "fernando", displayName: "Persona fernando", summary: "Massa de dados sintética." });
    expect(JSON.stringify(persona)).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-4/);
  });
});
