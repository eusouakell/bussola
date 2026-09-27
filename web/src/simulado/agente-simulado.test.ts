import { describe, expect, it } from "vitest";
import type { EventoAdk, Dados } from "../agente/tipos";
import { MODELO_INICIAL, type ModeloSessao } from "../sessao/modelo";
import { reducerSessao, type AcaoSessao } from "../sessao/reducer";
import { AgenteSimulado, MotorSimulado, fatiar, relogioFixo } from "./agente-simulado";
import { gerarRoteiro, MENSAGENS_ROTEIRO } from "./roteiro";
import * as T from "./textos";
import { brl, meses } from "../formatacao/formatar";
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

  it("recomenda o acelerado: 1660.85 por 19 meses", () => {
    const eventos = turno("Me mostra os caminhos");
    const cenarios = dados(respostas(eventos).comparar_cenarios).cenarios as { nome: string; aporte_mensal: number; prazo_meses: number }[];
    expect(cenarios.find((c) => c.nome === "acelerado")).toMatchObject({ aporte_mensal: 1660.85, prazo_meses: 19 });
    expect(eventos.some((e) => e.customMetadata?.bussola?.recomendado === "acelerado")).toBe(true);
    const rag = dados(respostas(eventos).buscar_contexto_financeiro).trechos as { score: number }[];
    expect(rag).toHaveLength(3);
  });

  it("julho: desvio de −776.32 puxado por Viagens e duas rotas", () => {
    const r = dados(respostas(turno("Avançar um mês")).avancar_mes);
    expect(r).toMatchObject({
      anomes: 202507,
      realizado: 884.53,
      desvio: -776.32,
      tolerancia: 166.09,
      status: "desvio",
      acumulado: 884.53,
      restante: 29115.47,
      meses_decorridos: 1,
      meses_restantes: 18,
    });
    expect(r.categoria_desvio).toMatchObject({ macro: "Viagens", valor_mes: 935.14, media_base: 6.51, aumento: 928.63 });
    const [a, b] = r.rotas as Dados[];
    expect(a).toMatchObject({ id: "A", aporte_mensal: 1617.53, prazo_meses: 18, prazo_total_meses: 19 });
    expect(b).toMatchObject({ id: "B", aporte_mensal: 1660.85, prazo_meses: 18, prazo_total_meses: 19 });
  });

  it("agosto com a rota A: folga e acumulado 5103.27", () => {
    const r = dados(respostas(turno("Avançar um mês", 1)).avancar_mes);
    expect(r).toMatchObject({ anomes: 202508, planejado: 1617.53, realizado: 4218.74, status: "folga", acumulado: 5103.27 });
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
    expect(dados(respostas(eventos).ajustar_plano)).toMatchObject({ rota: "B", aporte_mensal: 1660.85, prazo_meses: 19 });
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

  it("dezembro, com a rota A, fecha com desvio de −108.28", () => {
    const motor = motorAte(9);
    let dez: Dados = {};
    for (let i = 0; i < 4; i += 1) dez = dados(respostas(motor.turno("Avançar um mês")).avancar_mes);
    expect(dez).toMatchObject({ anomes: 202512, desvio: -108.28 });
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

  it("valores fora da demo, mas dentro da sobra, são simulados com os números do cliente", () => {
    const motor = motorAte(1);
    const eventos = motor.turno("R$ 50 mil em 3 anos");
    expect(dados(respostas(eventos).simular_objetivo)).toMatchObject({
      valor_alvo: 50000,
      prazo_meses: 36,
      aporte_mensal: 1388.89,
      viavel: true,
    });
    expect(textos(eventos).join(" ")).not.toMatch(/gravad/);
  });

  it("aporte livre simula pelo valor mensal", () => {
    const motor = motorAte(3);
    const r = dados(respostas(motor.turno("E se eu guardar R$ 2.000 por mês?")).simular_objetivo);
    expect(r).toMatchObject({ modo: "aporte", aporte_mensal: 2000, prazo_meses: 15, viavel: false });
  });
});

describe("BUG-01: atividade ilícita", () => {
  const PEDIDO = "gostaria de juntar 50 mil reais usando trafico de pessoas";

  it("bloqueia a frase do relato e não registra objetivo nenhum", () => {
    const motor = motorAte(0);
    const eventos = motor.turno(PEDIDO);
    const chamadas = eventos.flatMap((e) => (e.content?.parts ?? []).filter((p) => p.functionCall));
    expect(chamadas.map((p) => p.functionCall?.name)).toEqual([]);
    expect(motor.estadoAtual.objetivo).toBeUndefined();
    expect(eventos[0].customMetadata?.bussola?.guardrail).toBe("atividade_ilicita");
    expect(textos(eventos)[0]).toContain("Trabalho só com objetivos financeiros legítimos");
  });

  it("o plano para roubar um banco também é bloqueio, não resposta genérica", () => {
    const motor = motorAte(1);
    const eventos = motor.turno("gostaria de um plano para roubar um banco e pegar todo o dinheiro");
    expect(eventos[0].customMetadata?.bussola?.guardrail).toBe("atividade_ilicita");
    expect(textos(eventos).join(" ")).not.toContain(T.FORA_DO_ESCOPO_1);
  });
});

describe("BUG-02: fora do escopo escalona em vez de repetir", () => {
  const FORA = ["me da uma receita de pizza", "quem ganhou o oscar esse ano", "me ensina a fazer bolo", "conta uma piada"];

  it("quatro perguntas seguidas dão quatro respostas, nunca duas iguais em sequência", () => {
    const motor = motorAte(0);
    const falas = FORA.map((m) => textos(motor.turno(m)).join(" "));
    for (let i = 1; i < falas.length; i += 1) expect(falas[i], falas[i]).not.toBe(falas[i - 1]);
    expect(falas[0]).toBe(T.FORA_DO_ESCOPO_1);
    expect(falas[2]).toMatch(/canais de atendimento/);
    expect(falas[3]).toMatch(/atendimento do app/);
  });

  it("as respostas rápidas afunilam junto com o texto", () => {
    const motor = motorAte(0);
    const rapidas = () => motor.turno(FORA[0]).at(-1)?.customMetadata?.bussola?.respostas_rapidas ?? [];
    expect(rapidas()).toEqual(T.SUGESTOES_INICIAIS);
    expect(rapidas()).toEqual([T.SUGESTOES_INICIAIS[0], T.R_AJUDA]);
    expect(rapidas()).toEqual([T.R_AJUDA]);
  });

  it("uma intenção reconhecida zera o contador", () => {
    const motor = motorAte(0);
    const primeira = textos(motor.turno(FORA[0])).join(" ");
    motor.turno("Quero comprar meu primeiro apartamento");
    expect(textos(motor.turno(FORA[0])).join(" ")).toBe(primeira);
  });

  it("pergunta sobre empréstimo sem juros é tratada como dúvida de crédito", () => {
    const motor = motorAte(1);
    const eventos = motor.turno("como eu posso pegar emprestimo no itau sem nenhum juros?");
    expect(textos(eventos)[0]).toBe(T.DUVIDA_CREDITO);
    expect(textos(eventos)[0]).not.toBe(T.NAO_ENTENDI);
    expect(eventos.at(-1)?.customMetadata?.bussola?.respostas_rapidas).toEqual([T.R_FINANCIAMENTO, T.R_CONTINUAR]);
  });
});

describe("BUG-03: meta acima do perfil", () => {
  const META = "gostaria de comprar uma casa de 100 milhoes de reais em 2 anos";

  it("registra o sonho do cliente e faz a checagem de realidade com os números dele", () => {
    const motor = motorAte(0);
    const eventos = motor.turno(META);
    expect(dados(respostas(eventos).registrar_objetivo).objetivo).toMatchObject({ valor_alvo: 100000000, prazo_meses: 24 });
    expect(respostas(eventos).simular_objetivo).toBeUndefined();
    const texto = textos(eventos).join(" ");
    expect(texto).toContain(`${brl(100_000_000)} em ${meses(24)}`);
    expect(texto).toContain(`${brl(4_166_666.67)} por mês`); // valor ÷ prazo
    expect(texto).toContain(brl(1729)); // sobra mediana do golden de capacidade_poupanca
    expect(texto).toContain(`${brl(41_000)} em ${meses(24)}`); // meta intermediária vinda da sobra
  });

  it("propõe a meta intermediária e o prazo mais longo nas respostas rápidas", () => {
    const motor = motorAte(0);
    const rapidas = motor.turno(META).at(-2)?.customMetadata?.bussola?.respostas_rapidas;
    expect(rapidas).toEqual([`Começar com ${brl(41_000)} em ${meses(24)}`, `Alongar para ${meses(48)} e mirar ${brl(82_000)}`]);
  });

  it("a meta intermediária proposta é aceita e simulada", () => {
    const motor = motorAte(0);
    motor.turno(META);
    const eventos = motor.turno(`Começar com ${brl(41_000)} em ${meses(24)}`);
    expect(dados(respostas(eventos).simular_objetivo)).toMatchObject({ valor_alvo: 41000, aporte_mensal: 1708.33, viavel: true });
  });

  it("insistir muda o texto e o aviso da demonstração aparece uma única vez", () => {
    const motor = motorAte(0);
    const primeira = textos(motor.turno(META));
    const segunda = textos(motor.turno("quero 100 milhoes em 2 anos mesmo assim"));
    const terceira = textos(motor.turno("insisto: 100 milhoes em 2 anos"));
    // A checagem de realidade é o texto que repete o valor pedido pelo cliente.
    const checagem = (ts: string[]) => ts.find((t) => t.includes(brl(100_000_000)));
    expect(primeira).toContain(T.AVISO_SIMULACAO_GRAVADA);
    expect(segunda.join(" ")).not.toContain(T.AVISO_SIMULACAO_GRAVADA);
    expect(checagem(segunda)).not.toBe(checagem(primeira));
    expect(checagem(terceira)).not.toBe(checagem(segunda));
    expect(segunda.join(" ")).toContain("destino final");
  });

  it("renegociar o valor não repete o mesmo diagnóstico (BUG-05b)", () => {
    const motor = motorAte(0);
    const primeira = textos(motor.turno(META));
    const segunda = textos(motor.turno("quero 100 milhoes em 2 anos mesmo assim"));
    const diagnostico = primeira.find((t) => t.startsWith("Olhei seu extrato"));
    expect(diagnostico).toBeDefined();
    expect(segunda.some((t) => t.startsWith("Olhei seu extrato"))).toBe(false);
    // e a sobra reaproveitada continua alimentando a checagem de realidade
    expect(segunda.join(" ")).toContain(brl(1729));
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
