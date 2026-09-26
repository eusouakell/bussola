import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { EstadoSessao, EventoAdk } from "../agente/tipos";
import { FalhaConexao, type InicioSessao, type Modo, type Transporte } from "../agente/transporte";
import { useSessao } from "./useSessao";

const FALHA = "Não consegui falar com a Bússola agora.";

type Turno = (texto: string, sinal: AbortSignal | undefined, tentativa: number) => AsyncIterable<EventoAdk>;

interface OpcoesFalso {
  turno?: Turno;
  iniciar?: () => Promise<InicioSessao>;
  ressincronizar?: () => Promise<EstadoSessao | null>;
}

/** Transporte em memória: registra os envios e delega o turno ao teste. */
class TransporteFalso implements Transporte {
  readonly modo: Modo;
  readonly textos: string[] = [];
  readonly sinais: (AbortSignal | undefined)[] = [];
  readonly ressincronizar?: () => Promise<EstadoSessao | null>;
  private readonly opcoes: OpcoesFalso;

  constructor(modo: Modo, opcoes: OpcoesFalso) {
    this.modo = modo;
    this.opcoes = opcoes;
    this.ressincronizar = opcoes.ressincronizar;
  }

  iniciar(): Promise<InicioSessao> {
    return this.opcoes.iniciar?.() ?? Promise.resolve({ sessionId: "s-1", estado: { estado_jornada: "OBJETIVO" }, eventos: [] });
  }

  enviar(texto: string, sinal?: AbortSignal): AsyncIterable<EventoAdk> {
    this.textos.push(texto);
    this.sinais.push(sinal);
    return (this.opcoes.turno ?? respostaSimples)(texto, sinal, this.textos.length);
  }
}

/** Fábrica estável (criada fora do render) que guarda os transportes criados. */
function criarFabrica(opcoes: OpcoesFalso = {}) {
  const transportes: TransporteFalso[] = [];
  const fabrica = vi.fn((modo: Modo) => {
    const t = new TransporteFalso(modo, opcoes);
    transportes.push(t);
    return t;
  });
  return { fabrica, transportes, ultimo: () => transportes[transportes.length - 1] };
}

async function* respostaSimples(): AsyncIterable<EventoAdk> {
  yield { author: "bussola", partial: true, content: { parts: [{ text: "Olá" }] } };
  yield { author: "bussola", content: { parts: [{ text: "Olá, tudo certo." }] } };
}

function falhando(erro: Error): AsyncIterable<EventoAdk> {
  return { [Symbol.asyncIterator]: () => ({ next: () => Promise.reject(erro) }) };
}

/** Emite um parcial e só termina quando o sinal é abortado. */
async function* ateAbortar(_texto: string, sinal: AbortSignal | undefined): AsyncIterable<EventoAdk> {
  yield { author: "bussola", partial: true, content: { parts: [{ text: "Pensando" }] } };
  await new Promise<void>((resolve) => {
    if (sinal?.aborted) resolve();
    else sinal?.addEventListener("abort", () => resolve(), { once: true });
  });
}

/** Roda a ação dentro do act e espera as promessas do transporte assentarem. */
async function agir(acao: () => void = () => {}): Promise<void> {
  await act(async () => {
    acao();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function montar(fabrica: ReturnType<typeof criarFabrica>["fabrica"], modo: Modo = "simulado") {
  const hook = renderHook(() => useSessao(modo, fabrica));
  await agir();
  return hook;
}

describe("useSessao", () => {
  it("cria o transporte do modo e fica pronta depois de iniciar", async () => {
    const { fabrica } = criarFabrica();
    const { result } = await montar(fabrica);
    expect(fabrica).toHaveBeenCalledTimes(1);
    expect(fabrica).toHaveBeenCalledWith("simulado", { e3: false, e4: false, e5: false });
    expect(result.current.pronta).toBe(true);
    expect(result.current.modo).toBe("simulado");
    expect(result.current.modelo.estado.estado_jornada).toBe("OBJETIVO");
    expect(result.current.modelo.itens).toEqual([]);
  });

  it("enviar registra a mensagem do cliente, aplica os eventos e encerra o turno", async () => {
    const { fabrica, ultimo } = criarFabrica({
      ressincronizar: () => Promise.resolve({ estado_jornada: "ENTENDER" }),
    });
    const { result } = await montar(fabrica);

    act(() => result.current.enviar("  Quero viajar  "));
    expect(result.current.modelo.ocupado).toBe(true);
    expect(result.current.modelo.itens[0]).toMatchObject({ tipo: "mensagem_cliente", texto: "Quero viajar" });

    await agir();
    expect(ultimo().textos).toEqual(["Quero viajar"]);
    expect(ultimo().sinais[0]).toBeInstanceOf(AbortSignal);
    const { itens, ocupado, estado } = result.current.modelo;
    expect(ocupado).toBe(false);
    expect(itens.map((i) => i.tipo)).toEqual(["mensagem_cliente", "mensagem_agente"]);
    expect(itens[1]).toMatchObject({ texto: "Olá, tudo certo.", emStreaming: false });
    expect(estado.estado_jornada).toBe("ENTENDER");
  });

  it("ignora texto vazio e novo envio com o turno em andamento", async () => {
    const { fabrica, ultimo } = criarFabrica({ turno: ateAbortar });
    const { result } = await montar(fabrica);

    await agir(() => result.current.enviar("   "));
    expect(ultimo().textos).toEqual([]);
    expect(result.current.modelo.itens).toEqual([]);

    await agir(() => result.current.enviar("primeira"));
    await agir(() => result.current.enviar("segunda"));
    expect(ultimo().textos).toEqual(["primeira"]);
    expect(result.current.modelo.itens.filter((i) => i.tipo === "mensagem_cliente")).toHaveLength(1);
  });

  it("FalhaConexao no enviar vira falha_conexao com a mensagem fixa e o texto para reenviar", async () => {
    const { fabrica } = criarFabrica({ turno: () => falhando(new FalhaConexao("rede")) });
    const { result } = await montar(fabrica);

    await agir(() => result.current.enviar("Quero viajar"));
    const { itens, ocupado, erroConexao } = result.current.modelo;
    expect(ocupado).toBe(false);
    expect(erroConexao).toBe(FALHA);
    expect(itens.map((i) => i.tipo)).toEqual(["mensagem_cliente", "falha_conexao"]);
    expect(itens[1]).toMatchObject({ tipo: "falha_conexao", mensagem: FALHA, reenviar: "Quero viajar" });
  });

  it("repetir() reenvia o texto que falhou", async () => {
    const { fabrica, ultimo } = criarFabrica({
      turno: (_texto, _sinal, tentativa) => (tentativa === 1 ? falhando(new FalhaConexao("rede")) : respostaSimples()),
    });
    const { result } = await montar(fabrica);

    await agir(() => result.current.enviar("Quero viajar"));
    await agir(() => result.current.repetir());
    expect(ultimo().textos).toEqual(["Quero viajar", "Quero viajar"]);
    expect(result.current.modelo.itens.map((i) => i.tipo)).toEqual([
      "mensagem_cliente",
      "falha_conexao",
      "mensagem_cliente",
      "mensagem_agente",
    ]);
    expect(result.current.modelo.ocupado).toBe(false);
  });

  it("repetir() sem falha pendente não envia nada", async () => {
    const { fabrica, ultimo } = criarFabrica();
    const { result } = await montar(fabrica);
    await agir(() => result.current.enviar("oi"));
    await agir(() => result.current.repetir());
    expect(ultimo().textos).toEqual(["oi"]);
  });

  it('evento {"error": …} do SSE também deixa repetir() reenviar a última mensagem', async () => {
    const { fabrica, ultimo } = criarFabrica({
      turno: async function* (_texto, _sinal, tentativa) {
        yield tentativa === 1 ? { author: "sistema", error: "Falha no modelo" } : { author: "bussola", content: { parts: [{ text: "Oi" }] } };
      },
    });
    const { result } = await montar(fabrica);

    await agir(() => result.current.enviar("Quero viajar"));
    expect(result.current.modelo.itens.at(-1)).toMatchObject({ tipo: "falha_conexao", mensagem: FALHA, reenviar: "Quero viajar" });
    await agir(() => result.current.repetir());
    expect(ultimo().textos).toEqual(["Quero viajar", "Quero viajar"]);
  });

  it("iniciar que rejeita gera falha_conexao e a sessão não fica pronta", async () => {
    const { fabrica } = criarFabrica({ iniciar: () => Promise.reject(new FalhaConexao("rede")) });
    const { result } = await montar(fabrica);
    expect(result.current.pronta).toBe(false);
    expect(result.current.modelo.itens).toHaveLength(1);
    expect(result.current.modelo.itens[0]).toMatchObject({ tipo: "falha_conexao", mensagem: FALHA, reenviar: undefined });
  });

  it("ressincronizar que falha não vira falha de conexão", async () => {
    const { fabrica } = criarFabrica({ ressincronizar: () => Promise.reject(new Error("offline")) });
    const { result } = await montar(fabrica);
    await agir(() => result.current.enviar("oi"));
    expect(result.current.modelo.itens.map((i) => i.tipo)).toEqual(["mensagem_cliente", "mensagem_agente"]);
    expect(result.current.modelo.ocupado).toBe(false);
    expect(result.current.modelo.estado.estado_jornada).toBe("OBJETIVO");
  });

  it("parar() aborta o sinal passado ao transporte e fecha o turno sem falha", async () => {
    const { fabrica, ultimo } = criarFabrica({ turno: ateAbortar });
    const { result } = await montar(fabrica);

    await agir(() => result.current.enviar("oi"));
    const sinal = ultimo().sinais[0];
    expect(sinal?.aborted).toBe(false);
    expect(result.current.modelo.ocupado).toBe(true);
    expect(result.current.modelo.itens.at(-1)).toMatchObject({ tipo: "mensagem_agente", texto: "Pensando", emStreaming: true });

    await agir(() => result.current.parar());
    expect(sinal?.aborted).toBe(true);
    expect(result.current.modelo.ocupado).toBe(false);
    expect(result.current.modelo.itens.at(-1)).toMatchObject({ tipo: "mensagem_agente", emStreaming: false });
    expect(result.current.modelo.itens.some((i) => i.tipo === "falha_conexao")).toBe(false);

    await agir(() => result.current.enviar("de novo"));
    expect(ultimo().textos).toEqual(["oi", "de novo"]);
  });

  it('trocarModo("ao-vivo") limpa a conversa e chama a fábrica com o novo modo', async () => {
    const { fabrica, transportes } = criarFabrica();
    const { result } = await montar(fabrica);
    await agir(() => result.current.enviar("oi"));
    expect(result.current.modelo.itens).toHaveLength(2);

    await agir(() => result.current.trocarModo("ao-vivo"));
    expect(fabrica).toHaveBeenCalledTimes(2);
    expect(fabrica).toHaveBeenLastCalledWith("ao-vivo", { e3: false, e4: false, e5: false });
    expect(transportes.map((t) => t.modo)).toEqual(["simulado", "ao-vivo"]);
    expect(result.current.modo).toBe("ao-vivo");
    expect(result.current.pronta).toBe(true);
    expect(result.current.modelo.itens).toEqual([]);
    expect(result.current.modelo.auditoria.filter((a) => a.tipo_evento === "sessao_iniciada")).toHaveLength(1);

    await agir(() => result.current.enviar("ao vivo"));
    expect(transportes[0].textos).toEqual(["oi"]);
    expect(transportes[1].textos).toEqual(["ao vivo"]);
  });

  it("trocarModo para o mesmo modo não recria o transporte", async () => {
    const { fabrica } = criarFabrica();
    const { result } = await montar(fabrica);
    await agir(() => result.current.enviar("oi"));
    await agir(() => result.current.trocarModo("simulado"));
    expect(fabrica).toHaveBeenCalledTimes(1);
    expect(result.current.modelo.itens).toHaveLength(2);
  });

  it("trocarModo com turno em andamento aborta o sinal e descarta o turno antigo", async () => {
    const { fabrica, transportes } = criarFabrica({ turno: ateAbortar });
    const { result } = await montar(fabrica);
    await agir(() => result.current.enviar("oi"));

    await agir(() => result.current.trocarModo("ao-vivo"));
    expect(transportes[0].sinais[0]?.aborted).toBe(true);
    expect(result.current.modelo.itens).toEqual([]);
    expect(result.current.modelo.ocupado).toBe(false);
  });

  it("reiniciar recria a sessão no mesmo modo com as bordas configuradas", async () => {
    const { fabrica } = criarFabrica();
    const { result } = await montar(fabrica);
    await agir(() => result.current.enviar("oi"));

    await agir(() => result.current.configurarBordas({ e3: true }));
    expect(result.current.bordas).toEqual({ e3: true, e4: false, e5: false });

    await agir(() => result.current.reiniciar());
    expect(fabrica).toHaveBeenCalledTimes(2);
    expect(fabrica).toHaveBeenLastCalledWith("simulado", { e3: true, e4: false, e5: false });
    expect(result.current.modelo.itens).toEqual([]);
    expect(result.current.pronta).toBe(true);
  });

  it("desmontar aborta o turno em andamento", async () => {
    const { fabrica, ultimo } = criarFabrica({ turno: ateAbortar });
    const { result, unmount } = await montar(fabrica);
    await agir(() => result.current.enviar("oi"));
    unmount();
    expect(ultimo().sinais[0]?.aborted).toBe(true);
  });
});
