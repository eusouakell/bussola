// @vitest-environment node
// BFF de ponta a ponta: servidor HTTP real montado pelo composition root, com
// fixture de users temporária e um agente ADK falso que registra o que recebe.
import { randomBytes, randomUUID } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { createServer, request as httpRequest, type IncomingMessage, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { hashPassword } from "../infrastructure/auth/scryptPasswordVerifier.ts";
import { RecordingLogger } from "../test/fakes.ts";
import { loadConfig } from "./config.ts";
import { buildContainer } from "./container.ts";

interface AgentCall {
  method: string;
  url: string;
  body: unknown;
}

const SSE = 'data: {"content":{"parts":[{"text":"Olá"}]}}\n\n';
const password = randomBytes(12).toString("base64url");
const ids = { fernando: randomUUID(), bianca: randomUUID(), oculta: randomUUID() };

let dir: string;
let agentServer: Server;
let bffServer: Server;
let base: string;
let logger: RecordingLogger;
const agentCalls: AgentCall[] = [];
let agentRunStatus = 200;

function listen(server: Server): Promise<string> {
  return new Promise((done) => server.listen(0, "127.0.0.1", () => done(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)));
}

async function body(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of req as AsyncIterable<Buffer>) chunks.push(chunk);
  const text = Buffer.concat(chunks).toString();
  return text ? JSON.parse(text) : null;
}

/** Como o ADK: a sessão vive sob o `userId` e outro dono não a encontra. */
function fakeAgent(): Server {
  let counter = 0;
  const owners = new Map<string, string>();
  return createServer(async (req, res) => {
    const call = { method: req.method ?? "", url: req.url ?? "", body: await body(req) };
    agentCalls.push(call);
    const created = /^\/apps\/bussola_agent\/users\/([^/]+)\/sessions$/.exec(call.url);
    if (created && call.method === "POST") {
      counter += 1;
      const userId = decodeURIComponent(created[1]);
      const state = (call.body as { state?: unknown }).state;
      owners.set(`agente-${counter}`, userId);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ id: `agente-${counter}`, userId, state, events: [] }));
      return;
    }
    if (created && call.method === "GET") {
      const userId = decodeURIComponent(created[1]);
      const minhas = [...owners.entries()].filter(([, dono]) => dono === userId);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(minhas.map(([id], i) => ({ id, lastUpdateTime: i + 1, state: { id_usuario: ids[userId as keyof typeof ids] } }))));
      return;
    }
    const read = /^\/apps\/bussola_agent\/users\/([^/]+)\/sessions\/([^/]+)$/.exec(call.url);
    if (read && call.method === "GET") {
      const [userId, sessionId] = [decodeURIComponent(read[1]), decodeURIComponent(read[2])];
      if (owners.get(sessionId) !== userId) {
        res.writeHead(404).end();
        return;
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ id: sessionId, events: [] }));
      return;
    }
    if (call.url === "/run_sse" && call.method === "POST") {
      const turn = call.body as { userId?: string; sessionId?: string };
      if (owners.get(String(turn.sessionId)) !== turn.userId) {
        res.writeHead(404).end();
        return;
      }
      res.writeHead(agentRunStatus, { "Content-Type": "text/event-stream" });
      res.end(agentRunStatus === 200 ? SSE : "falhou");
      return;
    }
    res.writeHead(404).end();
  });
}

function writeFixtures(): { usersFixture: string; staticDir: string } {
  dir = mkdtempSync(join(tmpdir(), "bussola-bff-"));
  const usersFixture = join(dir, "users.json");
  const row = (login: string, id: string, featured: boolean) => ({
    login,
    id_usuario: id,
    display_name: `Persona ${login}`,
    summary: "Massa de dados sintética.",
    featured,
  });
  writeFileSync(
    usersFixture,
    JSON.stringify([row("fernando", ids.fernando, true), row("bianca", ids.bianca, true), row("oculta", ids.oculta, false)]),
  );
  const staticDir = join(dir, "dist");
  mkdirSync(join(staticDir, "assets"), { recursive: true });
  writeFileSync(join(staticDir, "index.html"), "<!doctype html><title>Bússola</title>");
  writeFileSync(join(staticDir, "assets", "app.js"), "console.log('ok')");
  writeFileSync(join(dir, "secret.txt"), "não servir");
  return { usersFixture, staticDir };
}

beforeAll(async () => {
  const { usersFixture, staticDir } = writeFixtures();
  agentServer = fakeAgent();
  const agentUrl = await listen(agentServer);
  const config = loadConfig(
    {
      AUTH_PASSWORD_HASH: await hashPassword(password),
      AGENT_URL: agentUrl,
      BUSSOLA_FAKES: "TRUE",
      USERS_FIXTURE: usersFixture,
      STATIC_DIR: staticDir,
    },
    { usersFixture },
  );
  logger = new RecordingLogger();
  const bff = buildContainer(config, logger);
  bffServer = createServer(bff.handler);
  base = await listen(bffServer);
  await bff.warmUp();
});

afterAll(async () => {
  await Promise.all([bffServer, agentServer].map((server) => new Promise((done) => server.close(done))));
  rmSync(dir, { recursive: true, force: true });
});

beforeEach(() => {
  agentCalls.length = 0;
  agentRunStatus = 200;
});

function post(path: string, payload: unknown, headers: Record<string, string> = {}): Promise<Response> {
  return fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: base, ...headers },
    body: JSON.stringify(payload),
  });
}

async function login(name: string): Promise<string> {
  const response = await post("/auth/login", { login: name, password });
  expect(response.status).toBe(200);
  const cookie = response.headers.getSetCookie()[0];
  return cookie.split(";", 1)[0];
}

async function agentSession(cookie: string): Promise<string> {
  const response = await post("/apps/bussola_agent/users/qualquer/sessions", {}, { Cookie: cookie });
  expect(response.status).toBe(200);
  return ((await response.json()) as { id: string }).id;
}

const runBody = (sessionId: string, extra: Record<string, unknown> = {}) => ({
  appName: "bussola_agent",
  userId: "qualquer",
  sessionId,
  newMessage: { role: "user", parts: [{ text: "quanto gastei?" }] },
  streaming: true,
  ...extra,
});

describe("BFF: autenticação", () => {
  it("lista só as personas em destaque, sem id_usuario", async () => {
    const response = await fetch(`${base}/auth/personas`);
    expect(response.status).toBe(200);
    const text = await response.text();
    expect(JSON.parse(text).personas.map((item: { login: string }) => item.login)).toEqual(["fernando", "bianca"]);
    for (const id of Object.values(ids)) expect(text).not.toContain(id);
  });

  it("login errado e login inexistente têm a mesma resposta", async () => {
    const wrong = await post("/auth/login", { login: "fernando", password: "senha-errada" });
    const unknown = await post("/auth/login", { login: "ninguem", password });
    expect(wrong.status).toBe(401);
    expect(unknown.status).toBe(401);
    expect(await wrong.json()).toEqual(await unknown.json());
    expect(wrong.headers.getSetCookie()).toEqual([]);
  });

  it("login certo emite cookie HttpOnly e SameSite=Strict e /auth/me devolve a persona", async () => {
    const response = await post("/auth/login", { login: "Fernando", password });
    expect(response.status).toBe(200);
    const [cookie] = response.headers.getSetCookie();
    expect(cookie).toMatch(/^bussola_session=[\w-]{43}; Path=\/; HttpOnly; SameSite=Strict; Max-Age=28800$/);
    expect(await response.json()).toEqual({
      usuario: { login: "fernando", displayName: "Persona fernando", summary: "Massa de dados sintética." },
    });
    const me = await fetch(`${base}/auth/me`, { headers: { Cookie: cookie.split(";", 1)[0] } });
    expect(me.status).toBe(200);
    expect(((await me.json()) as { usuario: { login: string } }).usuario.login).toBe("fernando");
  });

  it("sem cookie, /auth/me é 401", async () => {
    const response = await fetch(`${base}/auth/me`);
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ erro: { codigo: "NAO_AUTENTICADO", mensagem: "Entre com uma persona para continuar." } });
  });

  it("logout revoga a sessão e limpa o cookie", async () => {
    const cookie = await login("fernando");
    const response = await post("/auth/logout", {}, { Cookie: cookie });
    expect(response.status).toBe(204);
    expect(response.headers.getSetCookie()[0]).toContain("Max-Age=0");
    expect((await fetch(`${base}/auth/me`, { headers: { Cookie: cookie } })).status).toBe(401);
  });

  it("escrita sem Origin ou de outra origem é 403", async () => {
    const missing = await fetch(`${base}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login: "fernando", password }),
    });
    const foreign = await post("/auth/login", { login: "fernando", password }, { Origin: "https://evil.example" });
    expect(missing.status).toBe(403);
    expect(foreign.status).toBe(403);
    expect(((await foreign.json()) as { erro: { codigo: string } }).erro.codigo).toBe("ORIGEM_RECUSADA");
  });

  it("recusa corpo que não é JSON (415) e corpo grande demais (413)", async () => {
    const form = await fetch(`${base}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Origin: base },
      body: "login=fernando",
    });
    expect(form.status).toBe(415);
    const large = await post("/auth/login", { login: "fernando", password: "x".repeat(2048) });
    expect(large.status).toBe(413);
  });

  it("depois de 5 falhas no mesmo login, até a senha certa recebe 429", async () => {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      expect((await post("/auth/login", { login: "oculta", password: "errada" })).status).toBe(401);
    }
    const blocked = await post("/auth/login", { login: "oculta", password });
    expect(blocked.status).toBe(429);
    expect(((await blocked.json()) as { erro: { codigo: string } }).erro.codigo).toBe("MUITAS_TENTATIVAS");
  });
});

describe("BFF: proxy do agente", () => {
  it("cria a sessão com o id_usuario da conta, ignorando o state do corpo e o usuário da URL", async () => {
    const cookie = await login("fernando");
    const response = await post(
      "/apps/bussola_agent/users/bianca/sessions",
      { state: { id_usuario: ids.bianca } },
      { Cookie: cookie },
    );
    expect(response.status).toBe(200);
    expect(agentCalls).toEqual([
      { method: "POST", url: "/apps/bussola_agent/users/fernando/sessions", body: { state: { id_usuario: ids.fernando } } },
    ]);
  });

  it("app desconhecido é 404 e não chega ao agente", async () => {
    const cookie = await login("fernando");
    const response = await post("/apps/outro_app/users/fernando/sessions", {}, { Cookie: cookie });
    expect(response.status).toBe(404);
    expect(agentCalls).toEqual([]);
  });

  it("run_sse repassa o SSE e manda ao agente só o texto", async () => {
    const cookie = await login("fernando");
    const sessionId = await agentSession(cookie);
    agentCalls.length = 0;
    const response = await post("/run_sse", runBody(sessionId), { Cookie: cookie });
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/event-stream; charset=utf-8");
    expect(await response.text()).toBe(SSE);
    expect(agentCalls).toEqual([
      {
        method: "POST",
        url: "/run_sse",
        body: {
          appName: "bussola_agent",
          userId: "fernando",
          sessionId,
          newMessage: { role: "user", parts: [{ text: "quanto gastei?" }] },
          streaming: true,
        },
      },
    ]);
  });

  it("run_sse com stateDelta é 400 e não chega ao agente", async () => {
    const cookie = await login("fernando");
    const sessionId = await agentSession(cookie);
    agentCalls.length = 0;
    const response = await post("/run_sse", runBody(sessionId, { stateDelta: { id_usuario: ids.bianca } }), { Cookie: cookie });
    expect(response.status).toBe(400);
    expect(agentCalls).toEqual([]);
  });

  it("sessão do agente de outra persona é 404 para leitura e para turno", async () => {
    const fernando = await login("fernando");
    const sessionId = await agentSession(fernando);
    const bianca = await login("bianca");
    agentCalls.length = 0;
    const read = await fetch(`${base}/apps/bussola_agent/users/bianca/sessions/${sessionId}`, { headers: { Cookie: bianca } });
    const run = await post("/run_sse", runBody(sessionId), { Cookie: bianca });
    expect(read.status).toBe(404);
    expect(run.status).toBe(404);
    // A pergunta chega ao agente sempre com o login do cookie, que é quem
    // decide a posse; o login de fernando nunca sai daqui.
    expect(agentCalls.map((c) => c.url)).toEqual([`/apps/bussola_agent/users/bianca/sessions/${sessionId}`, "/run_sse"]);
    expect(agentCalls[1].body).toMatchObject({ userId: "bianca", sessionId });
    expect(JSON.stringify(agentCalls)).not.toContain("fernando");
    const own = await fetch(`${base}/apps/bussola_agent/users/x/sessions/${sessionId}`, { headers: { Cookie: fernando } });
    expect(own.status).toBe(200);
  });

  it("falha do agente vira 502 com mensagem ao cliente", async () => {
    const cookie = await login("fernando");
    const sessionId = await agentSession(cookie);
    agentRunStatus = 500;
    const response = await post("/run_sse", runBody(sessionId), { Cookie: cookie });
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({
      erro: { codigo: "AGENTE_INDISPONIVEL", mensagem: "O assistente não respondeu. Tente de novo." },
    });
  });

  it("lista as conversas salvas da persona do cookie, não as da URL", async () => {
    const fernando = await login("fernando");
    const primeira = await agentSession(fernando);
    const segunda = await agentSession(fernando);
    const bianca = await login("bianca");
    const dela = await agentSession(bianca);
    agentCalls.length = 0;

    const resposta = await fetch(`${base}/apps/bussola_agent/users/fernando/sessions`, { headers: { Cookie: bianca } });
    expect(resposta.status).toBe(200);
    const conversas = (await resposta.json()) as { id: string; lastUpdateTime?: number }[];
    expect(conversas.map((c) => c.id)).toEqual([dela]);
    expect(conversas.map((c) => c.id)).not.toContain(primeira);
    expect(conversas.map((c) => c.id)).not.toContain(segunda);
    // O login da URL é decorativo: quem busca é o cookie.
    expect(agentCalls.map((c) => c.url)).toEqual(["/apps/bussola_agent/users/bianca/sessions"]);
    expect(JSON.stringify(conversas)).not.toContain(ids.fernando);
  });

  it("sem login, listar conversas é 401", async () => {
    const response = await fetch(`${base}/apps/bussola_agent/users/fernando/sessions`);
    expect(response.status).toBe(401);
    expect(agentCalls).toEqual([]);
  });

  it("sem login, criar sessão do agente é 401", async () => {
    const response = await post("/apps/bussola_agent/users/fernando/sessions", {});
    expect(response.status).toBe(401);
    expect(agentCalls).toEqual([]);
  });
});

describe("BFF: front e cabeçalhos", () => {
  function rawGet(path: string): Promise<{ status: number; body: string }> {
    return new Promise((done, fail) => {
      httpRequest(`${base}${path}`, (res) => {
        let text = "";
        res.on("data", (chunk: Buffer) => (text += chunk.toString()));
        res.on("end", () => done({ status: res.statusCode ?? 0, body: text }));
      })
        .on("error", fail)
        .end();
    });
  }

  it("serve o index, o fallback da SPA e assets imutáveis", async () => {
    const index = await fetch(`${base}/`);
    expect(await index.text()).toContain("Bússola");
    const spa = await fetch(`${base}/extrato/marco`);
    expect(spa.headers.get("content-type")).toBe("text/html; charset=utf-8");
    const asset = await fetch(`${base}/assets/app.js`);
    expect(asset.headers.get("cache-control")).toBe("public, max-age=31536000, immutable");
  });

  it("não sai da pasta do front nem responde API com a SPA", async () => {
    for (const path of ["/../secret.txt", "/..%2fsecret.txt", "/assets/../../secret.txt"]) {
      const response = await rawGet(path);
      expect(response.status, path).toBe(404);
      expect(response.body, path).not.toContain("não servir");
    }
    const api = await fetch(`${base}/auth/desconhecida`);
    expect(api.status).toBe(404);
    expect(api.headers.get("content-type")).toContain("application/json");
  });

  it("toda resposta leva os cabeçalhos de segurança, inclusive erro", async () => {
    for (const path of ["/", "/healthz", "/auth/me"]) {
      const response = await fetch(`${base}${path}`);
      expect(response.headers.get("content-security-policy"), path).toContain("default-src 'self'");
      expect(response.headers.get("x-content-type-options"), path).toBe("nosniff");
      expect(response.headers.get("x-frame-options"), path).toBe("DENY");
      expect(response.headers.get("strict-transport-security"), path).toBeNull();
    }
  });

  it("os logs não trazem senha, token, cookie nem texto de mensagem", () => {
    const logged = JSON.stringify(logger.entries);
    expect(logger.entries.length).toBeGreaterThan(0);
    expect(logged).not.toContain(password);
    expect(logged).not.toContain("quanto gastei");
    expect(logged).not.toContain("bussola_session");
    expect(logged).not.toContain("senha-errada");
  });
});
