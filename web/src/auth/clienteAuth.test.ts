import { describe, expect, it, vi } from "vitest";
import { ClienteAuth } from "./clienteAuth";
import { FalhaAuth } from "./portal";

const FERNANDO = { login: "fernando", displayName: "Fernando", summary: "Cliente âncora." };

function json(status: number, corpo: unknown): Response {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
}

function cliente(...respostas: (Response | Error)[]) {
  const fetch = vi.fn<typeof globalThis.fetch>();
  for (const r of respostas) {
    if (r instanceof Error) fetch.mockRejectedValueOnce(r);
    else fetch.mockResolvedValueOnce(r);
  }
  return { fetch, auth: new ClienteAuth({ fetch }) };
}

describe("ClienteAuth", () => {
  it("lista só as personas bem formadas", async () => {
    const { fetch, auth } = cliente(json(200, { personas: [FERNANDO, { login: "sem-nome" }] }));
    await expect(auth.listarPersonas()).resolves.toEqual([FERNANDO]);
    expect(fetch).toHaveBeenCalledWith("/auth/personas", { credentials: "same-origin" });
  });

  it("entra com login e senha no corpo JSON e devolve a persona", async () => {
    const { fetch, auth } = cliente(json(200, { usuario: FERNANDO }));
    await expect(auth.entrar("fernando", "senha-de-teste")).resolves.toEqual(FERNANDO);
    const [caminho, init] = fetch.mock.calls[0];
    expect(caminho).toBe("/auth/login");
    expect(init).toMatchObject({ method: "POST", credentials: "same-origin" });
    expect(JSON.parse(String(init?.body))).toEqual({ login: "fernando", password: "senha-de-teste" });
  });

  it("repassa a mensagem do envelope de erro do BFF", async () => {
    const { auth } = cliente(json(401, { erro: { codigo: "CREDENCIAIS_INVALIDAS", mensagem: "Login ou senha inválidos." } }));
    const falha = await auth.entrar("fernando", "errada").catch((e: unknown) => e);
    expect(falha).toBeInstanceOf(FalhaAuth);
    expect(falha).toMatchObject({ codigo: "CREDENCIAIS_INVALIDAS", message: "Login ou senha inválidos." });
  });

  it("sessão atual: persona com 200, null com 401", async () => {
    const { auth } = cliente(json(200, { usuario: FERNANDO }), json(401, { erro: { codigo: "NAO_AUTENTICADO", mensagem: "x" } }));
    await expect(auth.sessaoAtual()).resolves.toEqual(FERNANDO);
    await expect(auth.sessaoAtual()).resolves.toBeNull();
  });

  it("falha de rede ou resposta sem envelope vira mensagem padrão em pt-BR", async () => {
    const { auth } = cliente(new TypeError("offline"), new Response("<html>", { status: 502 }));
    await expect(auth.listarPersonas()).rejects.toMatchObject({ codigo: "REDE" });
    await expect(auth.sair()).rejects.toMatchObject({ codigo: "HTTP_502", message: expect.stringContaining("Tente de novo") });
  });
});
