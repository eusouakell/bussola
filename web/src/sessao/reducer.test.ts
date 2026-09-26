import { describe, expect, it } from "vitest";
import goldens from "../../fixtures/goldens.json";
import type { EventoAdk } from "../agente/tipos";
import { MODELO_INICIAL, type ItemCard, type ItemFerramenta, type ModeloSessao } from "./modelo";
import { aplicarDelta, reducerSessao, type AcaoSessao } from "./reducer";

const AGORA = 1_790_000_000_000;

function rodar(acoes: AcaoSessao[], inicial: ModeloSessao = MODELO_INICIAL): ModeloSessao {
  return acoes.reduce(reducerSessao, inicial);
}

function ev(evento: EventoAdk): AcaoSessao {
  return { tipo: "evento", evento, agora: AGORA };
}

function chamada(nome: string, id: string, args: Record<string, unknown> = {}): EventoAdk {
  return { author: "bussola", content: { role: "model", parts: [{ functionCall: { id, name: nome, args } }] } };
}

function resposta(nome: string, id: string, response: unknown): EventoAdk {
  return { author: "bussola", content: { role: "user", parts: [{ functionResponse: { id, name: nome, response } }] } };
}

const perfil = goldens.ferramentas.perfil_financeiro__ate_202506;
const capacidade = goldens.ferramentas.capacidade_poupanca__ate_202506;

const inicio: AcaoSessao = {
  tipo: "iniciada",
  estado: { estado_jornada: "OBJETIVO", ate_anomes: 202506 },
  eventos: [],
  agora: AGORA,
};

describe("aplicarDelta", () => {
  it("faz merge raso e ignora chaves temp:*", () => {
    const novo = aplicarDelta({ a: 1, objetivo: { tipo: "x" } }, { objetivo: { tipo: "y" }, "temp:rascunho": 1, b: 2 });
    expect(novo).toEqual({ a: 1, objetivo: { tipo: "y" }, b: 2 });
  });
});

describe("reducerSessao", () => {
  it("registra sessao_iniciada e o primeiro passo da jornada", () => {
    const m = rodar([inicio]);
    expect(m.auditoria.map((a) => a.tipo_evento)).toEqual(["sessao_iniciada", "estado_alterado"]);
    expect(m.jornada).toEqual([{ estado: "OBJETIVO", ts: AGORA }]);
  });

  it("acumula texto parcial no rascunho e o texto final substitui o rascunho no fim", () => {
    const m = rodar([
      inicio,
      { tipo: "enviada", texto: "Quero viajar", agora: AGORA },
      ev({ author: "bussola", partial: true, content: { parts: [{ text: "Estou " }] } }),
      ev({ author: "bussola", partial: true, content: { parts: [{ text: "olhando" }] } }),
    ]);
    const rascunho = m.itens.at(-1);
    expect(rascunho).toMatchObject({ tipo: "mensagem_agente", texto: "Estou olhando", emStreaming: true });

    const final = rodar(
      [
        ev(chamada("perfil_financeiro", "c1")),
        ev({ author: "bussola", content: { parts: [{ text: "Estou olhando seus meses." }] } }),
      ],
      m,
    );
    const mensagens = final.itens.filter((i) => i.tipo === "mensagem_agente");
    expect(mensagens).toHaveLength(1);
    expect(final.itens.at(-1)).toMatchObject({ tipo: "mensagem_agente", texto: "Estou olhando seus meses.", emStreaming: false });
    expect(final.rascunhos).toEqual({});
  });

  it("ignora partes de raciocínio (thought)", () => {
    const m = rodar([inicio, ev({ author: "bussola", content: { parts: [{ text: "pensando", thought: true }] } })]);
    expect(m.itens).toHaveLength(0);
  });

  it("functionCall vira linha consultando com parâmetros mascarados e auditoria", () => {
    const uuid = "36a2b1c4-0000-4000-8000-00000000" + "7269";
    const m = rodar([inicio, { tipo: "enviada", texto: "oi", agora: AGORA }, ev(chamada("perfil_financeiro", "c1", { id_usuario: uuid }))]);
    const linha = m.itens.at(-1) as ItemFerramenta;
    expect(linha).toMatchObject({ tipo: "ferramenta", nome: "perfil_financeiro", status: "consultando", turno: 1 });
    expect(linha.args.id_usuario).toBe("36a2…7269");
    expect(JSON.stringify(m)).not.toContain(uuid);
    expect(m.auditoria.at(-1)).toMatchObject({ tipo_evento: "ferramenta_chamada", resumo: "perfil_financeiro" });
  });

  it("perfil e capacidade do mesmo turno formam um único CardDiagnostico", () => {
    const m = rodar([
      inicio,
      { tipo: "enviada", texto: "30 mil em 2 anos", agora: AGORA },
      ev(chamada("perfil_financeiro", "c1")),
      ev(chamada("capacidade_poupanca", "c2")),
      ev(resposta("perfil_financeiro", "c1", perfil)),
      ev(resposta("capacidade_poupanca", "c2", { result: capacidade })),
    ]);
    const cards = m.itens.filter((i): i is ItemCard => i.tipo === "card");
    expect(cards).toHaveLength(1);
    expect(cards[0].componente).toBe("CardDiagnostico");
    expect(cards[0].complementos.capacidade_poupanca).toMatchObject({ tipo: "envelope" });
    const registro = m.ferramentas.find((f) => f.chamadaId === "c1");
    expect(registro).toMatchObject({ status: "ok", fonte: perfil.fonte, avisos: perfil.avisos });
    expect(m.itens.filter((i) => i.tipo === "ferramenta").every((i) => (i as ItemFerramenta).status === "ok")).toBe(true);
  });

  it("resposta sem chamada prévia cria a linha e casa por nome", () => {
    const m = rodar([inicio, ev(resposta("dividas_e_parcelas", "x9", goldens.ferramentas.dividas_e_parcelas__ate_202506))]);
    expect(m.itens.map((i) => i.tipo)).toEqual(["ferramenta", "card"]);
  });

  it("erro INDISPONIVEL marca a linha e não cria card; DADOS_INSUFICIENTES no perfil vira card com aviso", () => {
    const m = rodar([
      inicio,
      ev(chamada("oportunidades_corte", "c1")),
      ev(resposta("oportunidades_corte", "c1", { erro: { codigo: "INDISPONIVEL", mensagem: "detalhe técnico" } })),
      ev(chamada("perfil_financeiro", "c2")),
      ev(resposta("perfil_financeiro", "c2", { erro: { codigo: "DADOS_INSUFICIENTES", mensagem: "x" } })),
    ]);
    const linha = m.itens.find((i) => i.tipo === "ferramenta" && i.nome === "oportunidades_corte") as ItemFerramenta;
    expect(linha.status).toBe("erro");
    expect(m.ferramentas[0].codigoErro).toBe("INDISPONIVEL");
    const cards = m.itens.filter((i): i is ItemCard => i.tipo === "card");
    expect(cards).toHaveLength(1);
    expect(cards[0]).toMatchObject({ componente: "CardDiagnostico", resposta: { tipo: "erro", codigo: "DADOS_INSUFICIENTES" } });
    expect(JSON.stringify(m)).not.toContain("detalhe técnico");
  });

  it("stateDelta muda a jornada e audita consentimento pendente e decidido", () => {
    const pedido = { consent_id: "c-0001", status: "pendente" };
    const m = rodar([
      inicio,
      ev({ author: "bussola", actions: { stateDelta: { estado_jornada: "AGIR", consentimentos: { criar_plano: pedido } } } }),
      ev({
        author: "bussola",
        actions: { stateDelta: { consentimentos: { criar_plano: { ...pedido, status: "aceito", ts: "2026-09-26T14:32:00-03:00" } } } },
      }),
    ]);
    expect(m.estado.estado_jornada).toBe("AGIR");
    expect(m.jornada.map((j) => j.estado)).toEqual(["OBJETIVO", "AGIR"]);
    expect(m.auditoria.map((a) => a.tipo_evento)).toEqual([
      "sessao_iniciada",
      "estado_alterado",
      "estado_alterado",
      "consentimento_solicitado",
      "consentimento_decidido",
    ]);
    expect(m.auditoria[2].resumo).toBe("objetivo → agir");
  });

  it("solicitar_consentimento vira um único item de consentimento", () => {
    const dados = { consent_id: "c-0001", acao: "criar_plano", status: "pendente" };
    const env = { dados, fonte: { ferramenta: "solicitar_consentimento", tabelas: [] }, avisos: [] };
    const m = rodar([
      inicio,
      ev(chamada("solicitar_consentimento", "c1")),
      ev(resposta("solicitar_consentimento", "c1", env)),
      ev(resposta("solicitar_consentimento", "c1", env)),
    ]);
    expect(m.itens.filter((i) => i.tipo === "consentimento")).toHaveLength(1);
  });

  it("consentimento pendente no state cria o card e a resposta completa o pedido", () => {
    const dados = { consent_id: "c-0001", acao: "criar_plano", status: "pendente", o_que_faz: "registrar o plano" };
    const env = { dados, fonte: { ferramenta: "solicitar_consentimento", tabelas: [] }, avisos: [] };
    const m = rodar([
      inicio,
      ev({ author: "bussola", actions: { stateDelta: { consentimentos: { criar_plano: { consent_id: "c-0001", status: "pendente" } } } } }),
      ev({ ...resposta("solicitar_consentimento", "c1", env), actions: { stateDelta: {} } }),
    ]);
    const itens = m.itens.filter((i) => i.tipo === "consentimento");
    expect(itens).toHaveLength(1);
    expect(itens[0]).toMatchObject({ acao: "criar_plano", consentId: "c-0001", pedido: { o_que_faz: "registrar o plano" } });
  });

  it("avancar_mes com desvio gera divisor, planejado × realizado e rota recalculada", () => {
    const dados = { anomes: 202507, status: "desvio", categoria_desvio: { macro: "Viagens" }, rotas: [{ id: "A" }, { id: "B" }] };
    const m = rodar([
      inicio,
      ev(chamada("avancar_mes", "c1")),
      ev(resposta("avancar_mes", "c1", { dados, fonte: { ferramenta: "avancar_mes", tabelas: [] }, avisos: [] })),
    ]);
    expect(m.itens.filter((i) => i.tipo !== "ferramenta").map((i) => (i.tipo === "card" ? i.componente : i.tipo))).toEqual([
      "divisor_mes",
      "CardPlanejadoRealizado",
      "CardRotaRecalculada",
    ]);
    expect(m.auditoria.slice(-3).map((a) => a.tipo_evento)).toEqual([
      "acompanhamento_mes_avancado",
      "desvio_detectado",
      "rota_recalculada",
    ]);
  });

  it("metadados: respostas rápidas e tag na mensagem; guardrail vira alerta auditado", () => {
    const m = rodar([
      inicio,
      { tipo: "enviada", texto: "a", agora: AGORA },
      ev({
        author: "bussola",
        content: { parts: [{ text: "Posso ajudar." }] },
        customMetadata: { bussola: { respostas_rapidas: ["Me mostra"], tag: "diagnostico" } },
      }),
      { tipo: "enviada", texto: "b", agora: AGORA },
      ev({
        author: "bussola",
        content: { parts: [{ text: "Não posso fazer isso." }] },
        customMetadata: { bussola: { guardrail: "outro_cliente", respostas_rapidas: ["Continuar"] } },
      }),
    ]);
    expect(m.itens[1]).toMatchObject({ tipo: "mensagem_agente", tag: "diagnostico", respostasRapidas: ["Me mostra"] });
    expect(m.itens.at(-1)).toMatchObject({ tipo: "guardrail", motivo: "outro_cliente" });
    expect(m.auditoria.at(-1)).toMatchObject({ tipo_evento: "guardrail_bloqueio", resumo: "outro_cliente" });
  });

  it("evento de erro e falha encerram o turno com falha_conexao", () => {
    const m = rodar([
      inicio,
      { tipo: "enviada", texto: "oi", agora: AGORA },
      ev({ author: "bussola", partial: true, content: { parts: [{ text: "" }] } }),
      ev({ author: "bussola", error: "boom" }),
    ]);
    expect(m.ocupado).toBe(false);
    expect(m.itens.at(-1)).toMatchObject({ tipo: "falha_conexao", mensagem: "Não consegui falar com a Bússola agora." });
    expect(m.itens.some((i) => i.tipo === "mensagem_agente")).toBe(false);

    const f = rodar([{ tipo: "falha", mensagem: "Não consegui falar com a Bússola agora.", reenviar: "oi", agora: AGORA }], m);
    expect(f.itens.at(-1)).toMatchObject({ tipo: "falha_conexao", reenviar: "oi" });
  });

  it("turno_fim fecha o streaming e aplica o state autoritativo", () => {
    const m = rodar([
      inicio,
      { tipo: "enviada", texto: "oi", agora: AGORA },
      ev({ author: "bussola", partial: true, content: { parts: [{ text: "Oi" }] } }),
      { tipo: "turno_fim", estado: { estado_jornada: "ENTENDER", ate_anomes: 202506 }, agora: AGORA },
    ]);
    expect(m.ocupado).toBe(false);
    expect(m.itens.at(-1)).toMatchObject({ emStreaming: false, texto: "Oi" });
    expect(m.estado.estado_jornada).toBe("ENTENDER");
  });
});
