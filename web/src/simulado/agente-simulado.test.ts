import { describe, expect, it } from "vitest";
import type { EventoAdk, Dados } from "../agente/tipos";
import { MODELO_INICIAL, type ModeloSessao } from "../sessao/modelo";
import { reducerSessao, type AcaoSessao } from "../sessao/reducer";
import { AgenteSimulado, MotorSimulado, fatiar, relogioFixo } from "./agente-simulado";
import { gerarRoteiro, MENSAGENS_ROTEIRO } from "./roteiro";
import roteiroGravado from "../../fixtures/roteiro-demo.json";
import { R_OUTRO_OBJETIVO } from "../vistas/P1Encerramento";

function respostas(eventos: EventoAdk[]): Record<string, unknown> {
  const saida: Record<string, unknown> = {};
  for (const e of eventos) {
    for (const p of e.content?.parts ?? []) if (p.functionResponse) saida[p.functionResponse.name] = p.functionResponse.response;
  }
  return saida;
}

function textos(eventos: EventoAdk[]): string[] {
  return eventos.flatMap((e) => (e.content?.parts ?? []).filter((p) => p.text).map((p) => p.text as string));
}

function dados(r: unknown): Dados {
  return (r as { dados: Dados }).dados;
}

function motorAte(n: number, bordas = {}): MotorSimulado {
  const motor = new MotorSimulado(relogioFixo());
  motor.configurarBordas(bordas);
  motor.iniciar();
  for (const m of MENSAGENS_ROTEIRO.slice(0, n)) motor.turno(m);
  return motor;
}

function reduzir(eventosPorTurno: { mensagem: string | null; eventos: EventoAdk[] }[]): ModeloSessao {
  const acoes: AcaoSessao[] = [];
  let agora = 1_790_000_000_000;
  for (const t of eventosPorTurno) {
    agora += 1000;
    if (t.mensagem === null) {
      acoes.push({ tipo: "iniciada", estado: {}, eventos: t.eventos, agora });
      continue;
    }
    acoes.push({ tipo: "enviada", texto: t.mensagem, agora });
    for (const evento of t.eventos) acoes.push({ tipo: "evento", evento, agora });
    acoes.push({ tipo: "turno_fim", agora });
  }
  return acoes.reduce(reducerSessao, MODELO_INICIAL);
}

describe("MotorSimulado: jornada canônica", () => {
  const roteiro = gerarRoteiro();
  const turno = (mensagem: string, ordem = 0) => roteiro.turnos.filter((t) => t.mensagem === mensagem)[ordem].eventos;

  it("é determinístico e igual ao roteiro gravado em fixtures/", () => {
    expect(gerarRoteiro()).toEqual(roteiro);
    expect(roteiro).toEqual(roteiroGravado);
  });

  it("simula 30 mil em 24 meses com os números do golden", () => {
    const r = dados(respostas(turno("R$ 30 mil em 2 anos")).simular_objetivo);
    expect(r).toMatchObject({ aporte_mensal: 1250, folga_mensal: 479, viavel: true });
  });

  it("recomenda o acelerado: 1681.15 por 18 meses", () => {
    const eventos = turno("Me mostra os caminhos");
    const cenarios = dados(respostas(eventos).comparar_cenarios).cenarios as { nome: string; aporte_mensal: number; prazo_meses: number }[];
    expect(cenarios.find((c) => c.nome === "acelerado")).toMatchObject({ aporte_mensal: 1681.15, prazo_meses: 18 });
    expect(eventos.some((e) => e.customMetadata?.bussola?.recomendado === "acelerado")).toBe(true);
    const rag = dados(respostas(eventos).buscar_contexto_financeiro).trechos as { score: number }[];
    expect(rag).toHaveLength(3);
  });

  it("julho: desvio de −796.62 puxado por Viagens e duas rotas", () => {
    const r = dados(respostas(turno("Avançar um mês")).avancar_mes);
    expect(r).toMatchObject({
      anomes: 202507,
      realizado: 884.53,
      desvio: -796.62,
      tolerancia: 168.12,
      status: "desvio",
      acumulado: 884.53,
      restante: 29115.47,
      meses_decorridos: 1,
      meses_restantes: 17,
    });
    expect(r.categoria_desvio).toMatchObject({ macro: "Viagens", valor_mes: 935.14, media_base: 6.51, aumento: 928.63 });
    const [a, b] = r.rotas as Dados[];
    expect(a).toMatchObject({ id: "A", aporte_mensal: 1712.67, prazo_meses: 17, prazo_total_meses: 18 });
    expect(b).toMatchObject({ id: "B", aporte_mensal: 1681.15, prazo_meses: 18, prazo_total_meses: 19 });
  });

  it("agosto com a rota A: folga e acumulado 5103.27", () => {
    const r = dados(respostas(turno("Avançar um mês", 1)).avancar_mes);
    expect(r).toMatchObject({ anomes: 202508, planejado: 1712.67, realizado: 4218.74, status: "folga", acumulado: 5103.27 });
  });

  it("nenhum texto do agente usa palavras proibidas", () => {
    const tudo = roteiro.turnos.flatMap((t) => textos(t.eventos)).join(" ").toLowerCase();
    for (const proibida of ["garantido", "aprovado", "contrate agora"]) expect(tudo).not.toContain(proibida);
  });

  it("argumentos MCP levam só o id mascarado", () => {
    const json = JSON.stringify(roteiro);
    expect(json).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i);
    expect(json).toContain("36a2…7269");
  });
});

describe("MotorSimulado → reducer", () => {
  const modelo = reduzir(gerarRoteiro().turnos);

  it("percorre a jornada até ACOMPANHAR", () => {
    expect(modelo.jornada.map((p) => p.estado)).toEqual(["OBJETIVO", "ENTENDER", "ANTECIPAR", "ORIENTAR", "AGIR", "ACOMPANHAR"]);
    expect(modelo.estado.ate_anomes).toBe(202508);
  });

  it("audita consentimentos, plano, desvio, ajuste e os dois guardrails", () => {
    const tipos = modelo.auditoria.map((a) => a.tipo_evento);
    for (const t of [
      "consentimento_solicitado",
      "consentimento_decidido",
      "plano_criado",
      "acao_executada",
      "acompanhamento_mes_avancado",
      "desvio_detectado",
      "rota_recalculada",
      "plano_ajustado",
    ] as const) {
      expect(tipos).toContain(t);
    }
    const guardrails = modelo.auditoria.filter((a) => a.tipo_evento === "guardrail_bloqueio");
    expect(guardrails).toHaveLength(2);
  });

  it("E1 vira alerta; E2 fica como texto do agente", () => {
    const alertas = modelo.itens.filter((i) => i.tipo === "guardrail");
    expect(alertas).toHaveLength(1);
    const ultima = modelo.itens.at(-1);
    expect(ultima).toMatchObject({ tipo: "mensagem_agente", respostasRapidas: ["Simular um financiamento", "Continuar o plano"] });
  });

  it("cria um card de consentimento por pedido, com o que faz e o que não faz", () => {
    const cards = modelo.itens.filter((i) => i.tipo === "consentimento");
    expect(cards.map((c) => c.tipo === "consentimento" && c.acao)).toEqual(["criar_plano", "ajustar_plano"]);
    const primeiro = cards[0];
    expect(primeiro.tipo === "consentimento" && primeiro.pedido?.o_que_nao_faz).toBeTruthy();
  });
});

describe("MotorSimulado: consentimento", () => {
  it("recusa não cria plano e mantém AGIR", () => {
    const motor = motorAte(4);
    const eventos = motor.turno("Agora não");
    expect(respostas(eventos).criar_plano).toBeUndefined();
    expect(motor.estadoAtual.consentimentos?.criar_plano?.status).toBe("recusado");
    expect(motor.estadoAtual.plano_id).toBeUndefined();
  });

  it("resposta ambígua pede confirmação e segue pendente", () => {
    const motor = motorAte(4);
    const eventos = motor.turno("Sim, mas talvez depois");
    expect(textos(eventos)[0]).toMatch(/Só para confirmar/);
    expect(motor.estadoAtual.consentimentos?.criar_plano?.status).toBe("pendente");
    motor.turno("Sim, autorizo");
    expect(motor.estadoAtual.plano_id).toBe("p-0001");
  });

  it("avançar sem plano explica o que falta", () => {
    const motor = motorAte(3);
    const eventos = motor.turno("Avançar um mês");
    const r = respostas(eventos).avancar_mes as { erro: { codigo: string } };
    expect(r.erro.codigo).toBe("SEM_PLANO_ATIVO");
  });

  it("outro objetivo: sem plano pergunta o objetivo; com plano segue com o atual", () => {
    expect(textos(motorAte(0).turno(R_OUTRO_OBJETIVO)).at(-1)).toMatch(/Qual objetivo/);
    expect(textos(motorAte(6).turno(R_OUTRO_OBJETIVO)).at(-1)).toMatch(/já tem um plano ativo/);
  });

  it("rota B mantém o aporte e estende o prazo", () => {
    const motor = motorAte(6);
    motor.turno("Quero adotar a rota B");
    const eventos = motor.turno("Sim, autorizo");
    expect(dados(respostas(eventos).ajustar_plano)).toMatchObject({ rota: "B", aporte_mensal: 1681.15, prazo_meses: 19 });
  });

  it("depois de dezembro devolve FIM_DO_REPLAY", () => {
    const motor = motorAte(5);
    const codigos: string[] = [];
    for (let i = 0; i < 7; i += 1) {
      const r = respostas(motor.turno("Avançar um mês")).avancar_mes as { erro?: { codigo: string } };
      if (r.erro) codigos.push(r.erro.codigo);
    }
    expect(motor.estadoAtual.ate_anomes).toBe(202512);
    expect(codigos).toEqual(["FIM_DO_REPLAY"]);
  });

  it("dezembro, com a rota A, fecha com desvio de −203.42", () => {
    const motor = motorAte(9);
    let dez: Dados = {};
    for (let i = 0; i < 4; i += 1) dez = dados(respostas(motor.turno("Avançar um mês")).avancar_mes);
    expect(dez).toMatchObject({ anomes: 202512, desvio: -203.42 });
  });
});

describe("MotorSimulado: estados de borda", () => {
  it("E3: oportunidades indisponível uma vez; tentar de novo consulta", () => {
    const motor = motorAte(1, { e3: true });
    const r = respostas(motor.turno("R$ 30 mil em 2 anos"));
    expect(r.oportunidades_corte).toEqual({ erro: { codigo: "INDISPONIVEL", mensagem: expect.any(String) } });
    const retry = respostas(motor.turno("Tentar de novo: Oportunidades de corte"));
    expect(dados(retry.oportunidades_corte).categorias).toBeDefined();
  });

  it("E4: capacidade com dados insuficientes; o diagnóstico avisa", () => {
    const motor = motorAte(1, { e4: true });
    const eventos = motor.turno("R$ 30 mil em 2 anos");
    expect((respostas(eventos).capacidade_poupanca as { erro: { codigo: string } }).erro.codigo).toBe("DADOS_INSUFICIENTES");
    expect(textos(eventos).join(" ")).toMatch(/poucos meses de histórico/);
  });

  it("valores fora da demo redirecionam sem simular", () => {
    const motor = motorAte(1);
    const eventos = motor.turno("R$ 50 mil em 3 anos");
    expect(respostas(eventos).simular_objetivo).toBeUndefined();
    expect(textos(eventos)[0]).toMatch(/R\$ 30 mil em 24 meses/);
  });

  it("aporte livre simula pelo valor mensal", () => {
    const motor = motorAte(3);
    const r = dados(respostas(motor.turno("E se eu guardar R$ 2.000 por mês?")).simular_objetivo);
    expect(r).toMatchObject({ modo: "aporte", aporte_mensal: 2000, prazo_meses: 15, viavel: false });
  });
});

describe("AgenteSimulado (transporte)", () => {
  it("emite parciais antes do texto final e respeita o sinal de abortar", async () => {
    const agente = new AgenteSimulado({ relogio: relogioFixo(), parciais: true });
    const inicio = await agente.iniciar();
    expect(inicio.sessionId).toBe("sim-0001");
    const recebidos: EventoAdk[] = [];
    for await (const e of agente.enviar("Quero comprar meu primeiro apartamento")) recebidos.push(e);
    const parciais = recebidos.filter((e) => e.partial);
    const final = recebidos.filter((e) => !e.partial && e.content?.parts?.[0]?.text);
    expect(parciais.length).toBeGreaterThan(1);
    expect(parciais.map((e) => e.content?.parts?.[0]?.text).join("")).toBe(final[0].content?.parts?.[0]?.text);

    const controle = new AbortController();
    controle.abort();
    const depois: EventoAdk[] = [];
    for await (const e of agente.enviar("R$ 30 mil em 2 anos", controle.signal)) depois.push(e);
    expect(depois).toHaveLength(0);
  });

  it("reiniciar a sessão preserva as bordas ligadas", async () => {
    const agente = new AgenteSimulado({ relogio: relogioFixo() });
    agente.configurarBordas({ e5: true });
    await agente.iniciar();
    expect(agente.bordas.e5).toBe(true);
  });

  it("fatiar preserva o texto", () => {
    const texto = "Olhei seu extrato de jan–jun/2025. Sua renda média é de R$ 6.691,39.";
    expect(fatiar(texto).join("")).toBe(texto);
  });
});
