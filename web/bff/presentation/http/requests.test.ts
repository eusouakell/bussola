// @vitest-environment node
import { describe, expect, it } from "vitest";
import { HttpError } from "./httpErrors.ts";
import { parseLoginRequest, parseRunRequest } from "./requests.ts";

const run = (overrides: Record<string, unknown> = {}) => ({
  appName: "bussola_agent",
  userId: "qualquer",
  sessionId: "s1",
  newMessage: { role: "user", parts: [{ text: "oi" }] },
  streaming: true,
  ...overrides,
});

function rejected(fn: () => unknown): HttpError {
  try {
    fn();
  } catch (error) {
    if (error instanceof HttpError) return error;
    throw error;
  }
  throw new Error("esperava HttpError");
}

describe("parseRunRequest", () => {
  it("fica só com a sessão e o texto, em camelCase ou snake_case", () => {
    expect(parseRunRequest(run())).toEqual({ sessionId: "s1", text: "oi" });
    expect(
      parseRunRequest({ app_name: "x", user_id: "y", session_id: "s2", new_message: { parts: [{ text: "a" }, { text: "b" }] } }),
    ).toEqual({ sessionId: "s2", text: "a\nb" });
  });

  it.each([
    ["stateDelta", run({ stateDelta: { id_usuario: "outro" } })],
    ["state", run({ state: {} })],
    ["campo desconhecido", run({ invocationId: "x" })],
    ["papel diferente de user", run({ newMessage: { role: "model", parts: [{ text: "oi" }] } })],
    ["parte que não é texto", run({ newMessage: { parts: [{ inlineData: { data: "AAAA" } }] } })],
    ["texto com chamada de função", run({ newMessage: { parts: [{ text: "oi", functionCall: {} }] } })],
    ["mensagem com campo extra", run({ newMessage: { parts: [{ text: "oi" }], metadata: {} } })],
    ["sem partes", run({ newMessage: { parts: [] } })],
    ["partes demais", run({ newMessage: { parts: Array.from({ length: 9 }, () => ({ text: "a" })) } })],
    ["sessionId longo", run({ sessionId: "s".repeat(129) })],
    ["sessionId vazio", run({ sessionId: "" })],
    ["streaming não booleano", run({ streaming: "sim" })],
    ["corpo não objeto", ["oi"]],
  ])("recusa %s com 400", (_name, body) => {
    expect(rejected(() => parseRunRequest(body))).toMatchObject({ status: 400, code: "PEDIDO_INVALIDO" });
  });
});

describe("parseLoginRequest", () => {
  it("aceita só login e senha", () => {
    expect(parseLoginRequest({ login: "a", password: "b" })).toEqual({ login: "a", password: "b" });
    expect(rejected(() => parseLoginRequest({ login: "a", password: "b", id_usuario: "x" })).status).toBe(400);
    expect(rejected(() => parseLoginRequest(null)).status).toBe(400);
  });
});
