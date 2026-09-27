import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { ClienteAdk, memoriaLocal, type MemoriaConversa } from "./cliente-adk";
import type { EventoAdk } from "./tipos";
import { FalhaConexao } from "./transporte";

const APP = "bussola_agent";
const USUARIO = "fernando";
const SESSOES = `/apps/${APP}/users/${USUARIO}/sessions`;

const codificador = new TextEncoder();

type FetchFalso = Mock<typeof fetch>;

function json(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
}

function corpoSse(blocos: string[], sinal?: AbortSignal | null): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(c) {
      for (const b of blocos) c.enqueue(codificador.encode(b));
      // Como o fetch de verdade: abortar derruba o corpo com AbortError.
      if (sinal) sinal.addEventListener("abort", () => c.error(new DOMException("Aborted", "AbortError")), { once: true });
      else c.close();
    },
  });
}

function sse(blocos: string[], sinal?: AbortSignal | null): Response {
  return new Response(corpoSse(blocos, sinal), { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function bloco(evento: unknown): string {
  return `data: ${JSON.stringify(evento)}\n\n`;
}

async function coletar(eventos: AsyncIterable<EventoAdk>): Promise<EventoAdk[]> {
  const saida: EventoAdk[] = [];
  for await (const e of eventos) saida.push(e);
  return saida;
}

/** Memória sem `localStorage`: cada cliente do teste começa sem conversa lembrada. */
function memoriaVolatil(inicial: string | null = null): MemoriaConversa {
  let valor = inicial;
  return {
    ler: () => valor,
    gravar: (sessionId) => {
      valor = sessionId;
    },
    limpar: () => {
      valor = null;
    },
  };
}

function criar(f: FetchFalso, base?: string, memoria: MemoriaConversa = memoriaVolatil()): ClienteAdk {
  return new ClienteAdk({ app: APP, usuario: USUARIO, fetch: f, base, memoria });
}

/** Cliente com sessão `s-1` já criada; as próximas respostas vêm de `respostas`. */
async function comSessao(...respostas: (Response | Error)[]): Promise<{ cliente: ClienteAdk; f: FetchFalso }> {
  const f = vi.fn<typeof fetch>();
  f.mockResolvedValueOnce(json({ id: "s-1", state: { estado_jornada: "OBJETIVO" } }));
  for (const r of respostas) {
    if (r instanceof Error) f.mockRejectedValueOnce(r);
    else f.mockResolvedValueOnce(r);
  }
  const cliente = criar(f);
  await cliente.iniciar();
  return { cliente, f };
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("ClienteAdk.iniciar", () => {
  it("cria a sessão com POST {} e devolve id e state", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-1", state: { estado_jornada: "OBJETIVO" } }));
    const inicio = await criar(f).iniciar();
    expect(inicio).toEqual({ sessionId: "s-1", estado: { estado_jornada: "OBJETIVO" }, eventos: [], retomada: false });
    expect(f).toHaveBeenCalledTimes(1);
    const [url, init] = f.mock.calls[0];
    expect(url).toBe(SESSOES);
    expect(init).toMatchObject({ method: "POST", body: "{}", headers: { "Content-Type": "application/json" } });
  });

  it("usa o prefixo base e codifica app e usuário na rota", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-1" }));
    const cliente = new ClienteAdk({ app: "app x", usuario: "maria/silva", base: "http://agente:8000", fetch: f });
    const inicio = await cliente.iniciar();
    expect(f.mock.calls[0][0]).toBe("http://agente:8000/apps/app%20x/users/maria%2Fsilva/sessions");
    expect(inicio.estado).toEqual({});
  });

  it("sem fetch injetado usa o fetch global", async () => {
    const fetchGlobal = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-9" }));
    vi.stubGlobal("fetch", fetchGlobal);
    const inicio = await new ClienteAdk({ app: APP, usuario: USUARIO }).iniciar();
    expect(inicio.sessionId).toBe("s-9");
    expect(fetchGlobal).toHaveBeenCalledWith(SESSOES, expect.objectContaining({ method: "POST" }));
  });

  it("HTTP 500 vira FalhaConexao", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ detail: "Internal Server Error" }, 500));
    const erro = await criar(f)
      .iniciar()
      .catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(FalhaConexao);
    expect(erro).toMatchObject({ name: "FalhaConexao", message: "http 500" });
  });

  it("erro de rede vira FalhaConexao", async () => {
    const f = vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(criar(f).iniciar()).rejects.toThrow(FalhaConexao);
  });

  it("resposta sem id vira FalhaConexao e não abre sessão", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ state: {} }));
    const cliente = criar(f);
    await expect(cliente.iniciar()).rejects.toThrow(FalhaConexao);
    await expect(coletar(cliente.enviar("oi"))).rejects.toThrow("sem sessão");
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("corpo que não é JSON vira FalhaConexao", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response("<html>proxy</html>", { status: 200 }));
    await expect(criar(f).iniciar()).rejects.toThrow(FalhaConexao);
  });
});

describe("ClienteAdk: conversa lembrada", () => {
  const HISTORICO = [
    { author: "user", timestamp: 1_700_000_000, content: { role: "user", parts: [{ text: "Quero viajar" }] } },
    { author: "bussola", timestamp: 1_700_000_001, content: { parts: [{ text: "Vamos montar o plano." }] } },
  ];

  it("com uma conversa lembrada, faz GET dela e devolve o histórico como retomada", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-7", state: { estado_jornada: "ENTENDER" }, events: HISTORICO }));
    const inicio = await criar(f, undefined, memoriaVolatil("s-7")).iniciar();
    expect(inicio).toEqual({
      sessionId: "s-7",
      estado: { estado_jornada: "ENTENDER" },
      eventos: HISTORICO,
      retomada: true,
    });
    expect(f).toHaveBeenCalledTimes(1);
    expect(f.mock.calls[0][0]).toBe(`${SESSOES}/s-7`);
  });

  it("conversa lembrada que não existe mais (404) abre uma nova e esquece a antiga", async () => {
    const f = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(json({ detail: "Not Found" }, 404))
      .mockResolvedValueOnce(json({ id: "s-8" }));
    const memoria = memoriaVolatil("s-7");
    const inicio = await criar(f, undefined, memoria).iniciar();
    expect(inicio).toMatchObject({ sessionId: "s-8", eventos: [], retomada: false });
    expect(memoria.ler()).toBe("s-8");
    expect(f.mock.calls.map((c) => c[0])).toEqual([`${SESSOES}/s-7`, SESSOES]);
  });

  it("lembra a conversa criada e retoma a mesma na recarga", async () => {
    const memoria = memoriaVolatil();
    const criando = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-9" }));
    await criar(criando, undefined, memoria).iniciar();
    expect(memoria.ler()).toBe("s-9");

    const recarga = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-9", events: HISTORICO }));
    const depois = await criar(recarga, undefined, memoria).iniciar();
    expect(depois).toMatchObject({ sessionId: "s-9", retomada: true });
    expect(depois.eventos).toHaveLength(2);
  });

  it("esquecer faz a próxima abertura criar conversa nova", async () => {
    const memoria = memoriaVolatil();
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-1" })).mockResolvedValueOnce(json({ id: "s-2" }));
    const cliente = criar(f, undefined, memoria);
    await cliente.iniciar();
    cliente.esquecer();
    expect(memoria.ler()).toBeNull();
    await expect(coletar(cliente.enviar("oi"))).rejects.toThrow("sem sessão");
    expect(await cliente.iniciar()).toMatchObject({ sessionId: "s-2", retomada: false });
    expect(f.mock.calls.map((c) => c[0])).toEqual([SESSOES, SESSOES]);
  });

  it("sem memória injetada, guarda o id no localStorage por app e persona", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-5" }));
    await new ClienteAdk({ app: APP, usuario: USUARIO, fetch: f }).iniciar();
    expect(localStorage.getItem(`bussola.conversa.${APP}.${USUARIO}`)).toBe("s-5");
    // Outra persona não herda a conversa: a chave é outra.
    expect(localStorage.getItem(`bussola.conversa.${APP}.bianca`)).toBeNull();
  });

  it("memoriaLocal sobrevive a localStorage indisponível", () => {
    const original = globalThis.localStorage;
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      get() {
        throw new Error("bloqueado");
      },
    });
    try {
      const memoria = memoriaLocal("bussola.conversa.x");
      expect(memoria.ler()).toBeNull();
      memoria.gravar("s-1");
      expect(memoria.ler()).toBe("s-1");
      memoria.limpar();
      expect(memoria.ler()).toBeNull();
    } finally {
      Object.defineProperty(globalThis, "localStorage", { configurable: true, value: original });
    }
  });

  it("retomar uma conversa específica traz o histórico e passa a ser a lembrada", async () => {
    const memoria = memoriaVolatil("s-1");
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ id: "s-3", state: {}, events: HISTORICO }));
    const cliente = criar(f, undefined, memoria);
    const inicio = await cliente.retomar("s-3");
    expect(inicio).toMatchObject({ sessionId: "s-3", retomada: true });
    expect(memoria.ler()).toBe("s-3");
    expect(f.mock.calls[0][0]).toBe(`${SESSOES}/s-3`);
  });

  it("retomar conversa inexistente é FalhaConexao", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ detail: "Not Found" }, 404));
    await expect(criar(f).retomar("s-3")).rejects.toThrow(FalhaConexao);
  });
});

describe("ClienteAdk.listar", () => {
  it("devolve as conversas com horário em ms e o objetivo como título", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValueOnce(
      json([
        { id: "s-2", lastUpdateTime: 1_700_000_100, state: { objetivo: { descricao: " Viagem ao Japão " } } },
        { id: "s-1" },
        { semId: true },
      ]),
    );
    const conversas = await criar(f).listar();
    expect(conversas).toEqual([
      { sessionId: "s-2", atualizadaEm: 1_700_000_100_000, titulo: "Viagem ao Japão" },
      { sessionId: "s-1", atualizadaEm: undefined, titulo: undefined },
    ]);
    expect(f.mock.calls[0][0]).toBe(SESSOES);
  });

  it("HTTP de erro, rede ou corpo que não é lista viram FalhaConexao", async () => {
    await expect(criar(vi.fn<typeof fetch>().mockResolvedValueOnce(json({ detail: "x" }, 500))).listar()).rejects.toThrow(FalhaConexao);
    await expect(criar(vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError("Failed to fetch"))).listar()).rejects.toThrow(
      FalhaConexao,
    );
    await expect(criar(vi.fn<typeof fetch>().mockResolvedValueOnce(json({ sessions: [] }))).listar()).rejects.toThrow(FalhaConexao);
    await expect(criar(vi.fn<typeof fetch>().mockResolvedValueOnce(new Response("nope", { status: 200 }))).listar()).rejects.toThrow(
      FalhaConexao,
    );
  });
});

describe("ClienteAdk.enviar", () => {
  it("sem sessão lança FalhaConexao sem chamar a rede", async () => {
    const f = vi.fn<typeof fetch>();
    await expect(coletar(criar(f).enviar("oi"))).rejects.toThrow(FalhaConexao);
    expect(f).not.toHaveBeenCalled();
  });

  it("faz POST /run_sse com o corpo do contrato e emite os eventos em ordem", async () => {
    const { cliente, f } = await comSessao(
      sse([
        ": ping\n\n",
        bloco({ author: "bussola", partial: true, content: { parts: [{ text: "Vou olhar" }] } }),
        bloco({ author: "bussola", content: { parts: [{ functionCall: { id: "c1", name: "perfil_financeiro", args: {} } }] } }),
        bloco({ author: "bussola", content: { parts: [{ text: "Vou olhar seus meses." }] } }),
      ]),
    );
    const controle = new AbortController();
    const eventos = await coletar(cliente.enviar("Quero viajar", controle.signal));

    expect(f).toHaveBeenCalledTimes(2);
    const [url, init] = f.mock.calls[1];
    expect(url).toBe("/run_sse");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toEqual({ "Content-Type": "application/json", Accept: "text/event-stream" });
    expect(init?.signal).toBe(controle.signal);
    expect(JSON.parse(String(init?.body))).toEqual({
      appName: APP,
      userId: USUARIO,
      sessionId: "s-1",
      newMessage: { role: "user", parts: [{ text: "Quero viajar" }] },
      streaming: true,
    });
    expect(eventos.map((e) => e.content?.parts?.[0])).toEqual([
      { text: "Vou olhar" },
      { functionCall: { id: "c1", name: "perfil_financeiro", args: {} } },
      { text: "Vou olhar seus meses." },
    ]);
  });

  it('repassa data: {"error": …} como evento, sem lançar', async () => {
    const { cliente } = await comSessao(sse(['data: {"error": "Falha no modelo"}\n\n']));
    expect(await coletar(cliente.enviar("oi"))).toEqual([{ author: "sistema", error: "Falha no modelo" }]);
  });

  it("HTTP 500 no run_sse vira FalhaConexao", async () => {
    const { cliente } = await comSessao(json({ detail: "erro" }, 500));
    await expect(coletar(cliente.enviar("oi"))).rejects.toThrow("http 500");
  });

  it("erro de rede no run_sse vira FalhaConexao", async () => {
    const { cliente } = await comSessao(new TypeError("Failed to fetch"));
    await expect(coletar(cliente.enviar("oi"))).rejects.toThrow(FalhaConexao);
  });

  it("resposta 200 sem corpo vira FalhaConexao", async () => {
    const { cliente } = await comSessao(new Response(null, { status: 200 }));
    await expect(coletar(cliente.enviar("oi"))).rejects.toThrow(FalhaConexao);
  });

  it("corpo interrompido no meio vira FalhaConexao depois dos eventos que chegaram", async () => {
    let leituras = 0;
    const corpo = new ReadableStream<Uint8Array>(
      {
        pull(c) {
          leituras += 1;
          if (leituras === 1) c.enqueue(codificador.encode(bloco({ author: "a" })));
          else c.error(new TypeError("network error"));
        },
      },
      { highWaterMark: 0 },
    );
    const { cliente } = await comSessao(new Response(corpo, { status: 200 }));
    const autores: string[] = [];
    const erro = await (async () => {
      for await (const e of cliente.enviar("oi")) autores.push(e.author);
    })().catch((e: unknown) => e);
    expect(autores).toEqual(["a"]);
    expect(erro).toBeInstanceOf(FalhaConexao);
    expect(erro).toMatchObject({ message: "fluxo interrompido" });
  });

  it("abortado antes do fetch encerra sem lançar e sem eventos", async () => {
    const { cliente, f } = await comSessao();
    f.mockImplementationOnce(async (_url, init) => {
      if (init?.signal?.aborted) throw new DOMException("Aborted", "AbortError");
      return sse([bloco({ author: "a" })]);
    });
    const controle = new AbortController();
    controle.abort();
    expect(await coletar(cliente.enviar("oi", controle.signal))).toEqual([]);
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("abortado com a leitura pendente encerra sem lançar", async () => {
    const { cliente, f } = await comSessao();
    f.mockImplementationOnce(async (_url, init) => sse([bloco({ author: "a" })], init?.signal));
    const controle = new AbortController();
    const iterador = cliente.enviar("oi", controle.signal)[Symbol.asyncIterator]();

    const primeiro = await iterador.next();
    expect(primeiro).toEqual({ done: false, value: { author: "a" } });
    const pendente = iterador.next();
    controle.abort();
    await expect(pendente).resolves.toEqual({ done: true, value: undefined });
  });

  it("abortado entre eventos não emite o restante", async () => {
    const { cliente, f } = await comSessao();
    f.mockImplementationOnce(async (_url, init) => sse([bloco({ author: "a" }), bloco({ author: "b" })], init?.signal));
    const controle = new AbortController();
    const autores: string[] = [];
    for await (const e of cliente.enviar("oi", controle.signal)) {
      autores.push(e.author);
      controle.abort();
    }
    expect(autores).toEqual(["a"]);
  });
});

describe("ClienteAdk.ressincronizar", () => {
  it("sem sessão devolve null sem chamar a rede", async () => {
    const f = vi.fn<typeof fetch>();
    expect(await criar(f).ressincronizar()).toBeNull();
    expect(f).not.toHaveBeenCalled();
  });

  it("faz GET da sessão e devolve o state", async () => {
    const { cliente, f } = await comSessao(json({ id: "s-1", state: { estado_jornada: "ENTENDER", ate_anomes: 202506 } }));
    expect(await cliente.ressincronizar()).toEqual({ estado_jornada: "ENTENDER", ate_anomes: 202506 });
    const [url, init] = f.mock.calls[1];
    expect(url).toBe(`${SESSOES}/s-1`);
    expect(init?.method ?? "GET").toBe("GET");
  });

  it("devolve null em HTTP de erro, rede, state ausente ou JSON inválido", async () => {
    const { cliente } = await comSessao(
      json({ detail: "Not Found" }, 404),
      new TypeError("Failed to fetch"),
      json({ id: "s-1" }),
      new Response("não é json", { status: 200 }),
    );
    expect(await cliente.ressincronizar()).toBeNull();
    expect(await cliente.ressincronizar()).toBeNull();
    expect(await cliente.ressincronizar()).toBeNull();
    expect(await cliente.ressincronizar()).toBeNull();
  });
});
