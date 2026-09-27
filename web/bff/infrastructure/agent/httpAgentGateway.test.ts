// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { AgentUnavailable } from "../../application/errors.ts";
import { ChatMessage } from "../../domain/chatMessage.ts";
import { HttpAgentGateway } from "./httpAgentGateway.ts";

type Call = [URL, RequestInit];

function gateway(response: () => Response, options: { idTokens?: { idToken: (a: string) => Promise<string> } } = {}) {
  const fetch = vi.fn<(...args: Call) => Promise<Response>>(async () => response());
  const agent = new HttpAgentGateway({
    baseUrl: "https://bussola-agent.example.run.app",
    app: "bussola_agent",
    fetch: fetch as unknown as typeof globalThis.fetch,
    ...options,
  });
  return { agent, fetch };
}

describe("HttpAgentGateway", () => {
  it("cria a sessão com o state recebido e o usuário no caminho", async () => {
    const { agent, fetch } = gateway(() => Response.json({ id: "s1", state: {} }));
    const session = await agent.createSession("fernando", { id_usuario: "u" });

    expect(session.id).toBe("s1");
    const [url, init] = fetch.mock.calls[0];
    expect(String(url)).toBe("https://bussola-agent.example.run.app/apps/bussola_agent/users/fernando/sessions");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ state: { id_usuario: "u" } });
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("lê a sessão e devolve null no 404", async () => {
    const { agent, fetch } = gateway(() => new Response("{}", { status: 404 }));
    expect(await agent.getSession("fernando", "s/1")).toBeNull();
    expect(String(fetch.mock.calls[0][0])).toMatch(/\/sessions\/s%2F1$/);
  });

  it("monta o corpo do run_sse só com o texto e devolve os bytes do SSE", async () => {
    const { agent, fetch } = gateway(() => new Response("data: {}\n\n"));
    const events = await agent.streamRun(
      { userId: "fernando", sessionId: "s1", message: ChatMessage.create("oi") },
      new AbortController().signal,
    );
    const chunks: Uint8Array[] = [];
    for await (const chunk of events) chunks.push(chunk);
    expect(Buffer.concat(chunks).toString()).toBe("data: {}\n\n");

    const [url, init] = fetch.mock.calls[0];
    expect(String(url)).toBe("https://bussola-agent.example.run.app/run_sse");
    expect(JSON.parse(String(init.body))).toEqual({
      appName: "bussola_agent",
      userId: "fernando",
      sessionId: "s1",
      newMessage: { role: "user", parts: [{ text: "oi" }] },
      streaming: true,
    });
  });

  it("com OIDC, manda ID token com audience = origem do agente", async () => {
    const idToken = vi.fn(async () => "id-token");
    const { agent, fetch } = gateway(() => Response.json({ id: "s1" }), { idTokens: { idToken } });
    await agent.createSession("fernando", {});
    expect(idToken).toHaveBeenCalledWith("https://bussola-agent.example.run.app");
    expect(new Headers(fetch.mock.calls[0][1].headers).get("Authorization")).toBe("Bearer id-token");
  });

  it("erro HTTP ou de rede vira AgentUnavailable com código curto", async () => {
    await expect(gateway(() => new Response("", { status: 500 })).agent.createSession("f1", {})).rejects.toThrow(
      expect.objectContaining({ name: "AgentUnavailable", code: "HTTP_500" }),
    );
    const refused = gateway(() => new Response("detalhe", { status: 403 })).agent;
    const turn = { userId: "f1", sessionId: "s1", message: ChatMessage.create("oi") };
    await expect(refused.streamRun(turn, new AbortController().signal)).rejects.toThrow(AgentUnavailable);
    const offline = gateway(() => {
      throw new TypeError("fetch failed");
    });
    await expect(offline.agent.getSession("f1", "s1")).rejects.toThrow(AgentUnavailable);
  });

  it.each([
    { baseUrl: "file:///etc/passwd", app: "bussola_agent" },
    { baseUrl: "https://x.run.app", app: "../admin" },
  ])("recusa configuração inválida %j", (options) => {
    expect(() => new HttpAgentGateway(options)).toThrow();
  });
});
