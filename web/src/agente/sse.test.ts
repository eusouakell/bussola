import { describe, expect, it } from "vitest";
import { eventoDeDados, lerEventos, ParserSse } from "./sse";
import type { EventoAdk } from "./tipos";

const codificador = new TextEncoder();

/** Corpo SSE feito de pedaços já prontos (texto ou bytes crus). */
function fluxo(pedacos: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(c) {
      for (const p of pedacos) c.enqueue(typeof p === "string" ? codificador.encode(p) : p);
      c.close();
    },
  });
}

async function coletar(eventos: AsyncIterable<EventoAdk>): Promise<EventoAdk[]> {
  const saida: EventoAdk[] = [];
  for await (const e of eventos) saida.push(e);
  return saida;
}

function textoDe(e: EventoAdk): string | undefined {
  return e.content?.parts?.[0]?.text;
}

describe("ParserSse", () => {
  it("devolve o data: de um bloco completo", () => {
    const p = new ParserSse();
    expect(p.empurrar('data: {"author":"bussola"}\n\n')).toEqual(['{"author":"bussola"}']);
  });

  it("junta eventos parciais até a linha em branco", () => {
    const p = new ParserSse();
    expect(p.empurrar('data: {"au')).toEqual([]);
    expect(p.empurrar('thor":"bussola"}')).toEqual([]);
    expect(p.empurrar("\n")).toEqual([]);
    expect(p.empurrar("\n")).toEqual(['{"author":"bussola"}']);
  });

  it("separa vários blocos que chegam no mesmo pedaço", () => {
    const p = new ParserSse();
    expect(p.empurrar("data: 1\n\ndata: 2\n\ndata: 3")).toEqual(["1", "2"]);
    expect(p.empurrar("\n\n")).toEqual(["3"]);
  });

  it("ignora linhas vazias extras entre os blocos", () => {
    const p = new ParserSse();
    expect(p.empurrar("\n\n\ndata: a\n\n\n\ndata: b\n\n\n")).toEqual(["a", "b"]);
    expect(p.finalizar()).toEqual([]);
  });

  it("aceita \\r\\n como fim de linha, inclusive cortado entre pedaços", () => {
    const p = new ParserSse();
    expect(p.empurrar("data: a\r\n\r\ndata: b\r")).toEqual(["a"]);
    expect(p.empurrar("\n\r\n")).toEqual(["b"]);
  });

  it("junta várias linhas data: do mesmo bloco com \\n", () => {
    const p = new ParserSse();
    const [dados] = p.empurrar('data: {"author":\ndata: "bussola"}\n\n');
    expect(dados).toBe('{"author":\n"bussola"}');
    expect(eventoDeDados(dados)).toEqual({ author: "bussola" });
  });

  it("ignora comentários (:) e campos que não são data:", () => {
    const p = new ParserSse();
    expect(p.empurrar(": ping\n\n")).toEqual([]);
    expect(p.empurrar(": keepalive\nevent: message\nid: 7\nretry: 1000\ndata: x\n\n")).toEqual(["x"]);
  });

  it("tira só um espaço depois de data:", () => {
    const p = new ParserSse();
    expect(p.empurrar("data:sem-espaco\n\ndata:  dois-espacos\n\n")).toEqual(["sem-espaco", " dois-espacos"]);
  });

  it("finalizar devolve o último bloco sem linha em branco e esvazia o buffer", () => {
    const p = new ParserSse();
    expect(p.empurrar('data: {"author":"bussola"}')).toEqual([]);
    expect(p.finalizar()).toEqual(['{"author":"bussola"}']);
    expect(p.finalizar()).toEqual([]);
  });

  it("finalizar sem data: pendente não devolve nada", () => {
    const p = new ParserSse();
    p.empurrar(": só comentário");
    expect(p.finalizar()).toEqual([]);
  });
});

describe("eventoDeDados", () => {
  it("preserva o evento do ADK e o autor", () => {
    const evento = eventoDeDados('{"author":"orientador","partial":true,"content":{"parts":[{"text":"Oi"}]}}');
    expect(evento).toEqual({ author: "orientador", partial: true, content: { parts: [{ text: "Oi" }] } });
  });

  it("author ausente ou não textual vira bussola", () => {
    expect(eventoDeDados('{"content":{"parts":[{"text":"Oi"}]}}')).toMatchObject({ author: "bussola" });
    expect(eventoDeDados('{"author":42}')).toEqual({ author: "bussola" });
  });

  it('data: {"error": …} vira evento de erro do sistema', () => {
    expect(eventoDeDados('{"error": "Falha no modelo"}')).toEqual({ author: "sistema", error: "Falha no modelo" });
    expect(eventoDeDados('{"error": {"codigo": 500}}')).toEqual({ author: "sistema", error: "erro" });
  });

  it("error nulo não é erro", () => {
    expect(eventoDeDados('{"author":"bussola","error":null}')).toMatchObject({ author: "bussola" });
  });

  it("ignora JSON inválido e valores que não são objeto", () => {
    expect(eventoDeDados("{nao é json")).toBeNull();
    expect(eventoDeDados("")).toBeNull();
    expect(eventoDeDados("[1,2]")).toBeNull();
    expect(eventoDeDados("42")).toBeNull();
    expect(eventoDeDados('"texto"')).toBeNull();
    expect(eventoDeDados("null")).toBeNull();
  });
});

describe("lerEventos", () => {
  const texto = "Olá! Você guarda R$ 1.681,15 por mês — a meta está no caminho 🧭 ✓";
  const bloco = `data: ${JSON.stringify({ author: "bussola", content: { parts: [{ text: texto }] } })}\n\n`;

  it("emite um evento por bloco, na ordem, ignorando comentário e JSON inválido", async () => {
    const eventos = await coletar(
      lerEventos(
        fluxo([
          ": ping\n\n",
          'data: {"author":"bussola","partial":true,"content":{"parts":[{"text":"Olá"}]}}\n\n',
          "data: {quebrado\n\n",
          'data: {"author":"bussola","content":{"parts":[{"text":"Olá!"}]}}\n\n',
        ]),
      ),
    );
    expect(eventos.map((e) => [e.partial ?? false, textoDe(e)])).toEqual([
      [true, "Olá"],
      [false, "Olá!"],
    ]);
  });

  it("remonta caracteres multibyte cortados byte a byte", async () => {
    const bytes = codificador.encode(bloco);
    const eventos = await coletar(lerEventos(fluxo(Array.from(bytes, (b) => Uint8Array.of(b)))));
    expect(eventos).toHaveLength(1);
    expect(textoDe(eventos[0])).toBe(texto);
  });

  it("remonta um emoji cortado no meio entre dois pedaços", async () => {
    const bytes = codificador.encode(bloco);
    const corte = bytes.indexOf(0xf0) + 2;
    const eventos = await coletar(lerEventos(fluxo([bytes.slice(0, corte), bytes.slice(corte)])));
    expect(textoDe(eventos[0])).toBe(texto);
  });

  it("emite o último bloco mesmo sem a linha em branco final", async () => {
    const eventos = await coletar(lerEventos(fluxo(['data: {"author":"a"}\n\n', 'data: {"author":"b"}'])));
    expect(eventos.map((e) => e.author)).toEqual(["a", "b"]);
  });

  it("repassa o evento de erro do SSE", async () => {
    const eventos = await coletar(lerEventos(fluxo(['data: {"error": "Falha no modelo"}\n\n'])));
    expect(eventos).toEqual([{ author: "sistema", error: "Falha no modelo" }]);
  });

  it("aceita blocos com \\r\\n e várias linhas data:", async () => {
    const eventos = await coletar(lerEventos(fluxo(['data: {"author":\r\n', 'data: "bussola"}\r\n\r\n'])));
    expect(eventos).toEqual([{ author: "bussola" }]);
  });

  it("não lê nada com o sinal já abortado e libera o leitor", async () => {
    const corpo = fluxo([bloco]);
    const controle = new AbortController();
    controle.abort();
    expect(await coletar(lerEventos(corpo, controle.signal))).toEqual([]);
    expect(corpo.locked).toBe(false);
  });

  it("para de ler quando o sinal é abortado entre pedaços", async () => {
    const corpo = fluxo(['data: {"author":"a"}\n\n', 'data: {"author":"b"}\n\n']);
    const controle = new AbortController();
    const autores: string[] = [];
    for await (const e of lerEventos(corpo, controle.signal)) {
      autores.push(e.author);
      controle.abort();
    }
    expect(autores).toEqual(["a"]);
    expect(corpo.locked).toBe(false);
  });

  it("propaga o erro do corpo depois de emitir o que já chegou", async () => {
    // `pull` com highWaterMark 0: o erro só chega na segunda leitura.
    let leituras = 0;
    const corpo = new ReadableStream<Uint8Array>(
      {
        pull(c) {
          leituras += 1;
          if (leituras === 1) c.enqueue(codificador.encode('data: {"author":"a"}\n\n'));
          else c.error(new Error("conexão caiu"));
        },
      },
      { highWaterMark: 0 },
    );
    const autores: string[] = [];
    await expect(
      (async () => {
        for await (const e of lerEventos(corpo)) autores.push(e.author);
      })(),
    ).rejects.toThrow("conexão caiu");
    expect(autores).toEqual(["a"]);
  });
});
