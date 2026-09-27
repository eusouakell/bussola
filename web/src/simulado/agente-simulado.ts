// Agente simulado (research R5): mesma interface do transporte ao vivo e os
// mesmos eventos ADK que o ciclo 004 emitiria. MCP responde com os goldens
// literais; ferramentas locais saem de `locais.ts`. Sem rede e sem GCP.
import type { Dados, EstadoSessao, EventoAdk, MetadadosBussola, Parte } from "../agente/tipos";
import { SEM_BORDAS, type Bordas, type InicioSessao, type Transporte } from "../agente/transporte";
import { CONFIG } from "../config";
import { brl, meses } from "../formatacao/formatar";
import { nomeEmFrase } from "../sessao/catalogo";
import { detectarGuardrail, type Bloqueio } from "./guardrails";
import { lerConsentimento, lerIntencao, type RespostaConsentimento, type TipoObjetivo } from "./intencoes";
import * as L from "./locais";
import * as T from "./textos";

/** Relógio em milissegundos. */
export type Relogio = () => number;

export const RELOGIO_INICIO_ISO = "2026-09-26T14:30:00-03:00";

/** Relógio de teste e do gerador de fixtures: avança `passoMs` a cada leitura. */
export function relogioFixo(inicioIso = RELOGIO_INICIO_ISO, passoMs = 1000): Relogio {
  let t = Date.parse(inicioIso) - passoMs;
  return () => {
    t += passoMs;
    return t;
  };
}

// `Bordas` é parte do port `Transporte` (a UI liga, o transporte implementa).
export type { Bordas } from "../agente/transporte";

const AVISO_RAG = "Conteúdo educativo e geral, não é recomendação individual. Confira a norma em vigor no site do Banco Central.";
const TRECHOS_RECOMENDACAO = ["reserva-emergencia#1", "comprometimento-renda#1", "custo-efetivo-total#1"];
const DIAGNOSTICO = ["perfil_financeiro", "capacidade_poupanca", "dividas_e_parcelas", "oportunidades_corte"];

interface Pendente {
  acao: string;
  consent_id: string;
  resumo: string;
  cenario?: string;
  rota?: L.Rota;
}

interface Chamada {
  nome: string;
  args: Dados;
  executar: () => L.Resultado;
}

function pad(n: number): string {
  return String(n).padStart(4, "0");
}

/** Meta intermediária num número redondo, sempre para baixo: milhar a partir de R$ 10 mil, centena abaixo disso. */
function metaRedonda(bruto: number): number {
  const passo = bruto >= 10000 ? 1000 : 100;
  return Math.max(Math.floor(bruto / passo) * passo, passo);
}

/** Núcleo determinístico: texto do cliente → eventos ADK completos do turno. */
export class MotorSimulado {
  bordas: Bordas = { ...SEM_BORDAS };
  private estado: EstadoSessao = {};
  private contadores = { fc: 0, consent: 0, plano: 0, inv: 0, ev: 0 };
  private eventos: EventoAdk[] = [];
  private invocacao = "";
  private plano: L.PlanoVigente | null = null;
  private historico: L.ResultadoMes[] = [];
  private rotas: L.Rota[] = [];
  private pendente: Pendente | null = null;
  private e3Consumido = false;
  /** Turnos seguidos fora do escopo (BUG-02) e metas seguidas fora do perfil (BUG-03). */
  private foraDoEscopo = 0;
  private metasForaDoPerfil = 0;
  private avisoSimulacaoDito = false;
  /** Diagnóstico já emitido (chave de período/bordas) e a sobra que ele trouxe. */
  private diagnosticoEm: string | null = null;
  private sobraConhecida: number | null = null;
  private readonly relogio: Relogio;

  constructor(relogio: Relogio = Date.now) {
    this.relogio = relogio;
  }

  configurarBordas(bordas: Partial<Bordas>) {
    if (bordas.e3 && !this.bordas.e3) this.e3Consumido = false;
    this.bordas = { ...this.bordas, ...bordas };
  }

  get estadoAtual(): EstadoSessao {
    return this.estado;
  }

  iniciar(): EventoAdk[] {
    this.comecar();
    this.delta({ id_usuario: CONFIG.idUsuarioMascarado, ate_anomes: CONFIG.anomesInicial, estado_jornada: "OBJETIVO" });
    return this.fechar();
  }

  turno(texto: string): EventoAdk[] {
    this.comecar();
    const bloqueio = detectarGuardrail(texto);
    if (bloqueio) {
      this.guardrail(bloqueio);
      return this.fechar();
    }
    if (this.pendente) {
      const resposta = lerConsentimento(texto);
      if (resposta) {
        this.decidir(this.pendente, resposta);
        return this.fechar();
      }
    }
    this.intencao(texto);
    return this.fechar();
  }

  // ------------------------------------------------------------ eventos

  private comecar() {
    this.contadores.inv += 1;
    this.invocacao = `inv-${pad(this.contadores.inv)}`;
    this.eventos = [];
  }

  private fechar(): EventoAdk[] {
    return this.eventos;
  }

  private emitir(parcial: Omit<EventoAdk, "id" | "invocationId" | "author" | "timestamp">) {
    this.contadores.ev += 1;
    const evento: EventoAdk = {
      id: `ev-${pad(this.contadores.ev)}`,
      invocationId: this.invocacao,
      author: "bussola",
      timestamp: this.relogio() / 1000,
      ...parcial,
    };
    if (parcial.actions?.stateDelta) this.estado = { ...this.estado, ...parcial.actions.stateDelta };
    this.eventos.push(evento);
  }

  private delta(stateDelta: Dados) {
    this.emitir({ actions: { stateDelta } });
  }

  private falar(texto: string, meta: MetadadosBussola = {}) {
    this.emitir({
      content: { role: "model", parts: [{ text: texto }] },
      ...(Object.keys(meta).length > 0 ? { customMetadata: { bussola: meta } } : {}),
    });
  }

  private argsMcp(extra: Dados = {}): Dados {
    return { id_usuario: this.estado.id_usuario, ate_anomes: this.estado.ate_anomes, ...extra };
  }

  /** Chamadas em paralelo: um evento com as `functionCall`, outro com as respostas (e o `stateDelta`). */
  private chamar(chamadas: Chamada[], depois?: (resultados: L.Resultado[]) => Dados | undefined, meta?: MetadadosBussola) {
    const ids = chamadas.map(() => {
      this.contadores.fc += 1;
      return `fc-${pad(this.contadores.fc)}`;
    });
    const pedidos: Parte[] = chamadas.map((c, i) => ({ functionCall: { id: ids[i], name: c.nome, args: c.args } }));
    this.emitir({ content: { role: "model", parts: pedidos } });
    const resultados = chamadas.map((c) => c.executar());
    const respostas: Parte[] = chamadas.map((c, i) => ({
      functionResponse: { id: ids[i], name: c.nome, response: resultados[i] },
    }));
    const stateDelta = depois?.(resultados);
    this.emitir({
      content: { role: "user", parts: respostas },
      ...(stateDelta ? { actions: { stateDelta } } : {}),
      ...(meta ? { customMetadata: { bussola: meta } } : {}),
    });
    return resultados;
  }

  private chamarUma(nome: string, args: Dados, executar: () => L.Resultado, depois?: (r: L.Resultado) => Dados | undefined) {
    return this.chamar([{ nome, args, executar }], depois ? (rs) => depois(rs[0]) : undefined)[0];
  }

  private agoraIso(): string {
    return new Date(this.relogio()).toISOString();
  }

  // ------------------------------------------------------------ jornada

  private sugestoes(): string[] {
    return T.SUGESTOES_POR_ESTADO[this.estado.estado_jornada ?? "OBJETIVO"];
  }

  private objetivoCompleto(): boolean {
    const o = this.estado.objetivo;
    return typeof o?.valor_alvo === "number" && typeof o?.prazo_meses === "number";
  }

  private intencao(texto: string) {
    const i = lerIntencao(texto);
    if (i.tipo === "outro") return this.foraDeEscopo();
    this.foraDoEscopo = 0;
    // A insistência na meta só conta em turnos seguidos falando de valores.
    if (i.tipo !== "valores") this.metasForaDoPerfil = 0;
    switch (i.tipo) {
      case "objetivo":
        return this.objetivo(i.objetivo);
      case "valores":
        return this.valores(i.valor_alvo, i.prazo_meses);
      case "nao_sei_valor":
        return this.falar(T.SEM_VALOR, { respostas_rapidas: [T.R_VALORES_DEMO] });
      case "comparar":
        return this.comparar();
      case "outro_caminho":
        return this.falar(T.OUTRO_CAMINHO, { respostas_rapidas: ["E se eu guardar R$ 2.000 por mês?", T.R_ACELERADO] });
      case "aporte":
        return this.aporteLivre(i.aporte_mensal);
      case "escolher":
        return this.escolher(i.cenario);
      case "avancar_mes":
        return this.avancar();
      case "adotar_rota":
        return this.adotarRota(i.rota);
      case "lembretes":
        if (!this.plano) return this.semPlano();
        return this.pedirConsentimento(T.PEDIDO_LEMBRETES, T.PRECISO_AUTORIZACAO);
      case "financiamento":
        return this.pedirConsentimento(T.PEDIDO_FINANCIAMENTO, T.PRECISO_AUTORIZACAO);
      case "status":
        return this.status();
      case "manter":
        return this.falar(T.MANTER, { respostas_rapidas: [T.R_AVANCAR, T.R_STATUS] });
      case "diagnostico":
        return this.rediagnosticar();
      case "tentar_de_novo":
        return this.tentarDeNovo(i.ferramenta);
      case "continuar":
        return this.falar("Vamos seguir de onde paramos.", { respostas_rapidas: this.sugestoes() });
      case "novo_objetivo":
        return this.novoObjetivo();
      case "ajuda":
        return this.falar(T.AJUDA, { respostas_rapidas: this.sugestoes() });
      case "duvida_credito":
        return this.falar(T.DUVIDA_CREDITO, { respostas_rapidas: [T.R_FINANCIAMENTO, T.R_CONTINUAR] });
      default:
        return this.foraDeEscopo();
    }
  }

  /** BUG-02: redireciona ao escopo, escalonando a cada turno seguido fora dele. */
  private foraDeEscopo() {
    this.foraDoEscopo += 1;
    const estado = this.estado.estado_jornada ?? "OBJETIVO";
    if (this.foraDoEscopo === 1) {
      return this.falar(T.FORA_DO_ESCOPO_1, { respostas_rapidas: this.sugestoes() });
    }
    if (this.foraDoEscopo === 2) {
      return this.falar(T.foraDoEscopo2(estado), { respostas_rapidas: [this.sugestoes()[0], T.R_AJUDA] });
    }
    return this.falar(T.foraDoEscopoFinal(this.foraDoEscopo), { respostas_rapidas: [T.R_AJUDA] });
  }

  private guardrail(b: Bloqueio) {
    if (b.alerta) {
      this.falar(b.texto, { guardrail: b.motivo, respostas_rapidas: b.respostas_rapidas });
      return;
    }
    // E2: recusa em texto, sem alerta visual; o bloqueio vai só para a auditoria.
    this.falar(b.texto, { respostas_rapidas: b.respostas_rapidas });
    this.emitir({ customMetadata: { bussola: { guardrail: b.motivo } } });
  }

  private planoAtivo() {
    const descricao = this.estado.objetivo?.descricao ?? "o seu objetivo";
    this.falar(`Você já tem um plano ativo para “${descricao}”. Nesta demonstração, seguimos com ele.`, {
      respostas_rapidas: this.sugestoes(),
    });
  }

  /** "Começar outro objetivo" (P1): a demonstração acompanha um plano por vez. */
  private novoObjetivo() {
    if (this.plano) return this.planoAtivo();
    this.falar("Claro! Qual objetivo você quer tirar do papel?", { respostas_rapidas: T.SUGESTOES_INICIAIS });
  }

  private objetivo(tipo: TipoObjetivo) {
    if (this.plano) return this.planoAtivo();
    if (tipo === "dividas") {
      const [r] = this.chamar([
        { nome: "dividas_e_parcelas", args: this.argsMcp(), executar: () => L.goldenAte("dividas_e_parcelas", this.ate()) },
      ]);
      if (!L.ehErro(r)) {
        this.falar(T.dividas({ comprometimento: r.dados.comprometimento_renda_pct as number, juros: r.dados.juros_pagos_media as number }), {
          tag: "diagnostico",
          respostas_rapidas: [T.SUGESTOES_INICIAIS[0], T.SUGESTOES_INICIAIS[2]],
        });
      }
      return;
    }
    const { descricao, frase } = T.OBJETIVOS[tipo];
    this.chamarUma(
      "registrar_objetivo",
      { tipo, descricao, prioridade: "alta" },
      () => L.registrarObjetivo({ tipo, descricao, prioridade: "alta" }),
      (r) => (L.ehErro(r) ? undefined : { objetivo: r.dados.objetivo }),
    );
    this.falar(T.perguntaValores(frase), { respostas_rapidas: [T.R_VALORES_DEMO, "Ainda não sei o valor"] });
  }

  private valores(valorDito: number | null, prazoDito: number | null) {
    if (this.plano) {
      this.falar("Seu plano já está ativo. Para mudar a meta, nesta demonstração, reinicie a conversa.", {
        respostas_rapidas: this.sugestoes(),
      });
      return;
    }
    const atual = this.estado.objetivo ?? null;
    const valor = valorDito ?? atual?.valor_alvo ?? null;
    const prazo = prazoDito ?? atual?.prazo_meses ?? null;
    const tipo = atual?.tipo ?? "imovel";
    const descricao = atual?.descricao || T.OBJETIVOS.imovel.descricao;
    const args = { tipo, descricao, valor_alvo: valor, prazo_meses: prazo, prioridade: atual?.prioridade ?? "alta" };
    const completo = valor !== null && prazo !== null;
    const r = this.chamarUma(
      "registrar_objetivo",
      args,
      () => L.registrarObjetivo(args),
      (res) => (L.ehErro(res) ? undefined : { objetivo: res.dados.objetivo, ...(completo ? { estado_jornada: "ENTENDER" } : {}) }),
    );
    if (L.ehErro(r)) {
      this.falar("Não entendi os valores. Pode me dizer quanto quer juntar e em quanto tempo?", {
        respostas_rapidas: [T.R_VALORES_DEMO],
      });
      return;
    }
    if (!completo) {
      this.falar(prazo === null ? T.SO_VALOR : "Anotei o prazo. E quanto você quer juntar?", {
        respostas_rapidas: [T.R_VALORES_DEMO],
      });
      return;
    }
    const sobra = this.diagnosticarUmaVez();
    const necessario = L.r2(valor / prazo);
    if (sobra !== null && necessario > sobra) {
      this.metaAcimaDoPerfil({ valor, prazo, necessario, sobra, descricao });
      return;
    }
    this.metasForaDoPerfil = 0;
    const demo = valor === 30000 && prazo === 24;
    const [sim] = this.chamar([
      {
        nome: "simular_objetivo",
        args: this.argsMcp({ valor_alvo: valor, prazo_meses: prazo }),
        // Fora da meta gravada, a simulação vem da mesma função determinística das rotas.
        executar: () => (demo ? L.goldenAte("simular_objetivo", this.ate()) : L.simularObjetivo(valor, { prazo_meses: prazo }, this.ate())),
      },
    ]);
    if (!L.ehErro(sim)) {
      this.falar(T.simulacao(sim.dados as Parameters<typeof T.simulacao>[0]), { tag: "simulacao", respostas_rapidas: [T.R_CAMINHOS] });
    }
  }

  /**
   * BUG-03: o objetivo do cliente fica registrado; aqui vem a checagem de
   * realidade com os números dele e uma primeira etapa vinda da sobra mediana.
   */
  private metaAcimaDoPerfil(d: { valor: number; prazo: number; necessario: number; sobra: number; descricao: string }) {
    this.metasForaDoPerfil += 1;
    const intermediaria = metaRedonda(d.sobra * d.prazo);
    const prazoLongo = Math.min(d.prazo * 2, 360);
    const longa = metaRedonda(d.sobra * prazoLongo);
    const texto = T.metaForaDoPerfil(
      {
        descricao: d.descricao,
        valor_alvo: d.valor,
        prazo_meses: d.prazo,
        aporte_necessario: d.necessario,
        sobra_mediana: d.sobra,
        meta_intermediaria: intermediaria,
      },
      this.metasForaDoPerfil,
    );
    const respostas = [`Começar com ${brl(intermediaria)} em ${meses(d.prazo)}`];
    if (prazoLongo > d.prazo && longa > intermediaria && longa < d.valor) {
      respostas.push(`Alongar para ${meses(prazoLongo)} e mirar ${brl(longa)}`);
    }
    this.falar(texto, { tag: "simulacao", respostas_rapidas: respostas });
    if (!this.avisoSimulacaoDito) {
      this.avisoSimulacaoDito = true;
      this.falar(T.AVISO_SIMULACAO_GRAVADA);
    }
  }

  private ate(): number {
    return this.estado.ate_anomes ?? CONFIG.anomesInicial;
  }

  /** Devolve a sobra mediana da ferramenta (`null` quando indisponível), base da checagem de viabilidade. */
  /** Chave do diagnóstico: muda com o período e com as bordas que alteram o resultado. */
  private chaveDiagnostico(): string {
    return `${this.ate()}|${this.bordas.e4}|${this.bordas.e3 && !this.e3Consumido}`;
  }

  /**
   * BUG-03/BUG-05b: renegociar o valor não repete o mesmo diagnóstico. Na
   * primeira vez o bloco sai inteiro; depois só reaproveita a sobra já lida e
   * recoloca a jornada em ANTECIPAR (o `registrar_objetivo` a devolveu a
   * ENTENDER).
   */
  private diagnosticarUmaVez(): number | null {
    const chave = this.chaveDiagnostico();
    if (this.diagnosticoEm === chave) {
      this.delta({ estado_jornada: "ANTECIPAR" });
      return this.sobraConhecida;
    }
    return this.diagnosticar(true);
  }

  private diagnosticar(avancarJornada: boolean): number | null {
    const e3 = this.bordas.e3 && !this.e3Consumido;
    const e4 = this.bordas.e4;
    const executar = (nome: string) => (): L.Resultado => {
      if (nome === "oportunidades_corte" && e3) {
        this.e3Consumido = true;
        return L.erro("INDISPONIVEL", "tempo esgotado na consulta");
      }
      if (nome === "capacidade_poupanca" && e4) return L.erro("DADOS_INSUFICIENTES", "menos de 3 meses de histórico");
      return L.goldenAte(nome, this.ate());
    };
    const [perfil, capacidade, dividas] = this.chamar(
      DIAGNOSTICO.map((nome) => ({ nome, args: this.argsMcp(), executar: executar(nome) })),
      () => (avancarJornada ? { estado_jornada: "ANTECIPAR" } : undefined),
    );
    const dados = (r: L.Resultado) => (L.ehErro(r) ? null : r.dados);
    const p = dados(perfil);
    const sobra = dados(capacidade)?.sobra_mediana as number | undefined;
    const fonte = L.ehErro(perfil) ? null : perfil.fonte.periodo;
    this.falar(
      T.diagnostico({
        periodo: fonte ?? { inicio: 202501, fim: this.ate() },
        renda_media: p?.renda_media as number | undefined,
        sobra_mediana: sobra,
        comprometimento: dados(dividas)?.comprometimento_renda_pct as number | undefined,
        e3,
        e4,
      }),
      { tag: "diagnostico" },
    );
    this.diagnosticoEm = this.chaveDiagnostico();
    this.sobraConhecida = typeof sobra === "number" ? sobra : null;
    return this.sobraConhecida;
  }

  private rediagnosticar() {
    this.falar(T.REDIAGNOSTICO);
    this.diagnosticar(this.estado.estado_jornada === "ENTENDER");
    this.falar("Quer seguir daqui?", { respostas_rapidas: this.sugestoes() });
  }

  private exigirObjetivo(): boolean {
    if (this.objetivoCompleto()) return true;
    this.falar("Primeiro preciso saber quanto você quer juntar e em quanto tempo.", { respostas_rapidas: [T.R_VALORES_DEMO] });
    return false;
  }

  private comparar() {
    if (!this.exigirObjetivo()) return;
    const objetivo = this.estado.objetivo!;
    const golden = L.goldenAte("comparar_cenarios", this.ate());
    const cenarios = golden.dados.cenarios as L.Cenario[];
    const recomendado = cenarios.filter((c) => c.viavel).sort((a, b) => a.pct_capacidade - b.pct_capacidade)[0] ?? null;
    this.chamar(
      [
        {
          nome: "comparar_cenarios",
          args: this.argsMcp({ valor_alvo: objetivo.valor_alvo, prazo_meses: objetivo.prazo_meses }),
          executar: () => golden,
        },
        {
          nome: "buscar_contexto_financeiro",
          args: { consulta: "reserva de emergência, comprometimento da renda e custo efetivo total", k: 3 },
          executar: () => this.rag(),
        },
      ],
      (rs) => (L.ehErro(rs[0]) ? undefined : { cenarios: rs[0].dados, estado_jornada: "ORIENTAR" }),
      recomendado ? { recomendado: recomendado.nome } : undefined,
    );
    this.falar(
      T.comparacao({
        prazo_objetivo: objetivo.prazo_meses as number,
        recomendado,
        fora: cenarios.filter((c) => !c.viavel),
      }),
      {
        tag: "recomendacao",
        respostas_rapidas: [recomendado ? `Quero o caminho ${recomendado.nome}` : T.R_ACELERADO, T.R_OUTRO_CAMINHO],
        ...(recomendado ? { recomendado: recomendado.nome } : {}),
      },
    );
  }

  private rag(): L.Resultado {
    const scores = [0.82, 0.77, 0.71];
    const trechos = L.trechosRag(TRECHOS_RECOMENDACAO).map((t, i) => ({ ...t, score: scores[i] ?? 0.5 }));
    return {
      dados: { trechos },
      fonte: { ferramenta: "buscar_contexto_financeiro", tabelas: [] },
      avisos: [AVISO_RAG, L.avisoSimulado("003")],
    };
  }

  private aporteLivre(aporte: number) {
    if (!this.exigirObjetivo()) return;
    const valor = this.estado.objetivo!.valor_alvo as number;
    const r = this.chamarUma(
      "simular_objetivo",
      this.argsMcp({ valor_alvo: valor, aporte_mensal: aporte }),
      () => L.simularObjetivo(valor, { aporte_mensal: aporte }, this.ate()),
    );
    if (L.ehErro(r)) {
      this.falar("Não consegui simular esse valor. Pode tentar outro?", { respostas_rapidas: [T.R_ACELERADO] });
      return;
    }
    const d = r.dados;
    const premissas = d.premissas as { capacidade_mensal: number };
    this.falar(
      T.aporteLivre({
        aporte_mensal: d.aporte_mensal as number,
        valor_alvo: d.valor_alvo as number,
        prazo_meses: d.prazo_meses as number,
        viavel: d.viavel as boolean,
        capacidade: premissas.capacidade_mensal,
      }),
      { tag: "simulacao", respostas_rapidas: [T.R_ACELERADO, T.R_CAMINHOS] },
    );
  }

  private escolher(cenario: string) {
    if (this.plano) {
      this.falar("Seu plano já está ativo. Para acompanhar, avance um mês.", { respostas_rapidas: this.sugestoes() });
      return;
    }
    if (!this.estado.cenarios) {
      this.falar("Antes, deixa eu te mostrar os caminhos possíveis.", { respostas_rapidas: [T.R_CAMINHOS] });
      return;
    }
    const escolhido = L.cenarioDoGolden(cenario, this.ate());
    const objetivo = this.estado.objetivo!;
    this.chamarUma(
      "escolher_cenario",
      { cenario },
      () => L.escolherCenario(cenario),
      (r) => (L.ehErro(r) ? undefined : { cenario_escolhido: cenario, estado_jornada: "AGIR" }),
    );
    if (!escolhido) return;
    this.pedirConsentimento(
      T.pedidoPlano({
        aporte_mensal: escolhido.aporte_mensal,
        prazo_meses: escolhido.prazo_meses,
        valor_alvo: objetivo.valor_alvo as number,
        periodo: L.periodoDados(this.ate()),
        descricao: objetivo.descricao || T.OBJETIVOS.imovel.descricao,
      }),
      T.escolha(cenario, escolhido.viavel),
      { cenario },
    );
  }

  private pedirConsentimento(pedido: L.PedidoConsentimento, texto: string, extra: Partial<Pendente> = {}) {
    this.contadores.consent += 1;
    const consentId = `c-${pad(this.contadores.consent)}`;
    this.falar(texto, { tag: "acao" });
    this.chamarUma(
      "solicitar_consentimento",
      { acao: pedido.acao, resumo: pedido.resumo },
      () => L.solicitarConsentimento(consentId, pedido),
      () => ({
        consentimentos: {
          ...this.estado.consentimentos,
          [pedido.acao]: { consent_id: consentId, status: "pendente", resumo: pedido.resumo },
        },
      }),
    );
    this.pendente = { acao: pedido.acao, consent_id: consentId, resumo: pedido.resumo, ...extra };
  }

  private decidir(p: Pendente, resposta: RespostaConsentimento) {
    if (resposta === "ambiguo") {
      this.falar(T.CONFIRMAR, { tag: "acao", respostas_rapidas: [T.R_SIM, T.R_NAO] });
      return;
    }
    this.pendente = null;
    const status = resposta === "aceito" ? "aceito" : "recusado";
    this.delta({
      consentimentos: {
        ...this.estado.consentimentos,
        [p.acao]: { consent_id: p.consent_id, status, ts: this.agoraIso(), resumo: p.resumo },
      },
    });
    if (status === "recusado") {
      const proximas: Record<string, string[]> = {
        criar_plano: [T.R_ACELERADO, T.R_CAMINHOS],
        ajustar_plano: [T.R_MANTER, T.R_AVANCAR],
      };
      this.falar(T.RECUSA_RESPEITOSA, { respostas_rapidas: proximas[p.acao] ?? this.sugestoes() });
      return;
    }
    switch (p.acao) {
      case "criar_plano":
        return this.criarPlano(p.cenario ?? "acelerado");
      case "ajustar_plano":
        return p.rota ? this.ajustar(p.rota) : undefined;
      case "ativar_lembretes":
        this.chamarUma("ativar_lembretes", { plano_id: this.estado.plano_id }, () => L.ativarLembretes());
        return this.falar(T.LEMBRETES_OK, { tag: "acao", respostas_rapidas: this.sugestoes() });
      case "simular_contratacao":
        this.chamarUma("simular_contratacao", { tipo: "financiamento_generico" }, () => L.simularContratacao());
        return this.falar(T.FINANCIAMENTO_OK, { tag: "acao", respostas_rapidas: this.sugestoes() });
      default:
        return undefined;
    }
  }

  private novoPlanoId(): string {
    this.contadores.plano += 1;
    return `p-${pad(this.contadores.plano)}`;
  }

  private criarPlano(cenario: string) {
    const escolhido = L.cenarioDoGolden(cenario, this.ate());
    const objetivo = this.estado.objetivo;
    if (!escolhido || !objetivo) return;
    const plano: L.Plano = {
      plano_id: this.novoPlanoId(),
      cenario,
      valor_alvo: objetivo.valor_alvo as number,
      aporte_mensal: escolhido.aporte_mensal,
      prazo_meses: escolhido.prazo_meses,
      criado_em_anomes: this.ate(),
    };
    const r = this.chamarUma(
      "criar_plano",
      { cenario, consent_id: this.estado.consentimentos?.criar_plano?.consent_id },
      () => L.criarPlano(plano),
      (res) => (L.ehErro(res) ? undefined : { plano_id: plano.plano_id }),
    );
    if (L.ehErro(r)) return;
    this.plano = { ...plano, inicio_anomes: plano.criado_em_anomes };
    this.historico = [];
    this.falar(T.planoCriado(plano), { tag: "acao", respostas_rapidas: [T.R_AVANCAR, T.R_LEMBRETES] });
  }

  private semPlano() {
    this.falar(T.SEM_PLANO, { respostas_rapidas: this.estado.cenarios ? [T.R_ACELERADO] : [T.R_CAMINHOS] });
  }

  private avancar() {
    let registro: L.ResultadoMes | undefined;
    let rotas: L.Rota[] = [];
    const r = this.chamarUma(
      "avancar_mes",
      this.argsMcp({ plano_id: this.estado.plano_id ?? null }),
      () => {
        const saida = L.avancarMes(this.plano, this.ate(), this.historico);
        registro = saida.registro;
        if (!L.ehErro(saida.resultado)) rotas = saida.resultado.dados.rotas as L.Rota[];
        return saida.resultado;
      },
      () =>
        registro
          ? {
              ate_anomes: registro.anomes,
              estado_jornada: "ACOMPANHAR",
              acompanhamento: [...this.historico, registro].map((h) => ({ ...h })),
            }
          : undefined,
    );
    if (L.ehErro(r) || !registro) {
      const codigo = L.ehErro(r) ? r.erro.codigo : "";
      if (codigo === "FIM_DO_REPLAY") this.falar(T.FIM_REPLAY, { respostas_rapidas: [T.R_STATUS] });
      else this.semPlano();
      return;
    }
    this.historico = [...this.historico, registro];
    this.rotas = rotas;
    const d = r.dados;
    const fim = registro.anomes >= CONFIG.anomesFinal ? " Esse é o último mês da demonstração." : "";
    if (registro.status === "desvio") {
      const causa = d.categoria_desvio as { macro: string; valor_mes: number; media_base: number } | null;
      this.falar(
        T.mesDesvio({
          anomes: registro.anomes,
          realizado: registro.realizado,
          planejado: registro.planejado,
          desvio: registro.desvio,
          macro: causa?.macro,
          valor_mes: causa?.valor_mes,
          media_base: causa?.media_base,
        }) + fim,
        { tag: "diagnostico", respostas_rapidas: rotas.map((rota) => `Quero adotar a rota ${rota.id}`) },
      );
    } else if (registro.status === "folga") {
      this.falar(
        T.mesFolga({
          anomes: registro.anomes,
          realizado: registro.realizado,
          planejado: registro.planejado,
          acumulado: d.acumulado as number,
          percentual: d.percentual as number,
        }) + fim,
        { tag: "diagnostico", respostas_rapidas: [T.R_STATUS, T.R_MANTER] },
      );
    } else {
      this.falar(
        T.mesNoPlano({
          anomes: registro.anomes,
          realizado: registro.realizado,
          acumulado: d.acumulado as number,
          percentual: d.percentual as number,
        }) + fim,
        { tag: "diagnostico", respostas_rapidas: [T.R_AVANCAR, T.R_STATUS] },
      );
    }
  }

  private adotarRota(id: "A" | "B" | null) {
    if (!this.plano) return this.semPlano();
    if (this.rotas.length === 0) return this.falar(T.SEM_ROTA, { respostas_rapidas: [T.R_AVANCAR] });
    const rota = id ? this.rotas.find((r) => r.id === id) : undefined;
    if (!rota) {
      this.falar(T.QUAL_ROTA, { respostas_rapidas: this.rotas.map((r) => `Quero adotar a rota ${r.id}`) });
      return;
    }
    this.pedirConsentimento(
      T.pedidoAjuste({ rota: rota.id, titulo: rota.titulo, aporte_mensal: rota.aporte_mensal, prazo_meses: rota.prazo_meses }),
      T.PRECISO_AUTORIZACAO,
      { rota },
    );
  }

  private ajustar(rota: L.Rota) {
    if (!this.plano) return;
    const novoId = this.novoPlanoId();
    const r = this.chamarUma(
      "ajustar_plano",
      { plano_id: this.plano.plano_id, rota: rota.id, consent_id: this.estado.consentimentos?.ajustar_plano?.consent_id },
      () => L.ajustarPlano(novoId, rota),
      (res) => (L.ehErro(res) ? undefined : { plano_id: novoId }),
    );
    if (L.ehErro(r)) return;
    this.plano = { ...this.plano, plano_id: novoId, aporte_mensal: rota.aporte_mensal, prazo_meses: rota.prazo_total_meses };
    this.rotas = [];
    this.falar(T.planoAjustado({ aporte_mensal: rota.aporte_mensal, prazo_meses: rota.prazo_meses }), {
      tag: "acao",
      respostas_rapidas: [T.R_AVANCAR, T.R_STATUS],
    });
  }

  private status() {
    const r = this.chamarUma("status_plano", this.argsMcp({ plano_id: this.estado.plano_id ?? null }), () =>
      L.statusPlano(this.plano, (this.estado.objetivo as Dados | null) ?? null, this.historico),
    );
    if (L.ehErro(r)) return this.semPlano();
    this.falar(T.STATUS, { tag: "diagnostico", respostas_rapidas: [T.R_AVANCAR] });
  }

  private tentarDeNovo(nome: string) {
    if (!DIAGNOSTICO.includes(nome)) {
      this.falar(T.NAO_ENTENDI, { respostas_rapidas: this.sugestoes() });
      return;
    }
    const r = this.chamarUma(nome, this.argsMcp(), () => L.goldenAte(nome, this.ate()));
    if (!L.ehErro(r)) this.falar(T.retryOk(nomeEmFrase(nome)), { tag: "diagnostico", respostas_rapidas: this.sugestoes() });
  }
}

// ------------------------------------------------------------ transporte

export interface OpcoesSimulado {
  /** Relógio do motor (teste e gerador: `relogioFixo()`). */
  relogio?: Relogio;
  /** Quebra o texto final em pedaços `partial` antes do evento final (navegador). */
  parciais?: boolean;
  /** Latência base por ferramenta, em ms (0 nos testes). */
  atrasoMs?: number;
  esperar?: (ms: number, sinal?: AbortSignal) => Promise<void>;
}

function esperarPadrao(ms: number, sinal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (ms <= 0 || sinal?.aborted) return resolve();
    const t = setTimeout(resolve, ms);
    sinal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        resolve();
      },
      { once: true },
    );
  });
}

function textoDe(e: EventoAdk): string | null {
  const partes = e.content?.parts ?? [];
  if (partes.length !== 1 || typeof partes[0].text !== "string") return null;
  return partes[0].text;
}

/** Pedaços de ~3 palavras, preservando os espaços. */
export function fatiar(texto: string): string[] {
  const palavras = texto.match(/\S+\s*/g) ?? [texto];
  const saida: string[] = [];
  for (let i = 0; i < palavras.length; i += 3) saida.push(palavras.slice(i, i + 3).join(""));
  return saida;
}

export class AgenteSimulado implements Transporte {
  readonly modo = "simulado" as const;
  private motor: MotorSimulado;
  private sessoes = 0;
  private readonly opcoes: OpcoesSimulado;

  constructor(opcoes: OpcoesSimulado = {}) {
    this.opcoes = opcoes;
    this.motor = new MotorSimulado(opcoes.relogio);
  }

  get bordas(): Bordas {
    return this.motor.bordas;
  }

  configurarBordas(bordas: Partial<Bordas>) {
    this.motor.configurarBordas(bordas);
  }

  async iniciar(): Promise<InicioSessao> {
    const bordas = this.motor.bordas;
    this.motor = new MotorSimulado(this.opcoes.relogio);
    this.motor.configurarBordas(bordas);
    this.sessoes += 1;
    return { sessionId: `sim-${pad(this.sessoes)}`, estado: {}, eventos: this.motor.iniciar() };
  }

  async ressincronizar(): Promise<EstadoSessao | null> {
    return this.motor.estadoAtual;
  }

  async *enviar(texto: string, sinal?: AbortSignal): AsyncIterable<EventoAdk> {
    const eventos = this.motor.turno(texto);
    const esperar = this.opcoes.esperar ?? esperarPadrao;
    const base = this.opcoes.atrasoMs ?? 0;
    const fator = this.motor.bordas.e5 ? CONFIG.fatorLento : 1;
    const agora = () => (this.opcoes.relogio ?? Date.now)() / 1000;
    const carimbar = (e: EventoAdk): EventoAdk => (base > 0 ? { ...e, timestamp: agora() } : e);

    await esperar(base * 2 * fator, sinal);
    for (const evento of eventos) {
      if (sinal?.aborted) return;
      const texto = this.opcoes.parciais ? textoDe(evento) : null;
      if (texto) {
        for (const pedaco of fatiar(texto)) {
          if (sinal?.aborted) return;
          yield carimbar({
            author: evento.author,
            invocationId: evento.invocationId,
            timestamp: evento.timestamp,
            partial: true,
            content: { role: "model", parts: [{ text: pedaco }] },
          });
          await esperar((base > 0 ? 25 : 0) * fator, sinal);
        }
      }
      yield carimbar(evento);
      const chamada = evento.content?.parts?.some((p) => p.functionCall);
      await esperar((chamada ? base : base / 4) * fator, sinal);
    }
  }
}
