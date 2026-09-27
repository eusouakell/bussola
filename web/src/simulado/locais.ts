// Emulação das ferramentas locais dos ciclos 004–006 (contracts/eventos-agente.md §3).
// Funções puras: leem só os goldens e os argumentos. Números arredondados a 2
// casas aqui, na "ferramenta"; a UI só formata (constituição III).
import goldensJson from "../../fixtures/goldens.json";
import type { Dados, Envelope, ErroEnvelope, Fonte } from "../agente/tipos";
import { CONFIG } from "../config";
import { brl, meses, periodo } from "../formatacao/formatar";

export interface TrechoRag {
  doc_id: string;
  trecho_id: string;
  titulo: string;
  tema: string;
  texto: string;
  fonte: { nome: string; referencia: string; url: string | null };
}

interface Goldens {
  ferramentas: Record<string, Envelope>;
  rag_trechos: TrechoRag[];
}

const GOLDENS = goldensJson as unknown as Goldens;

/** Recorte gravado da demonstração (config: `VITE_BUSSOLA_ANOMES_*`). */
const ANOMES_INICIAL = CONFIG.anomesInicial;
const ANOMES_FINAL = CONFIG.anomesFinal;
const TOLERANCIA = 0.1;

export type Resultado = Envelope | ErroEnvelope;

export function ehErro(r: Resultado): r is ErroEnvelope {
  return "erro" in r;
}

/** Arredonda a 2 casas (meio para longe do zero), sem `-0`. */
export function r2(n: number): number {
  const v = (Math.sign(n) * Math.round(Math.abs(n) * 100 + 1e-9)) / 100;
  return v === 0 ? 0 : v;
}

function clonar<T>(valor: T): T {
  return JSON.parse(JSON.stringify(valor)) as T;
}

export function avisoSimulado(ciclo: string): string {
  return `Resposta simulada pelo front; regravar após o ciclo ${ciclo}`;
}

/** Golden literal (cópia) de `contracts/fixtures/ferramentas/{chave}.json`. */
export function golden(chave: string): Envelope {
  const env = GOLDENS.ferramentas[chave];
  if (!env) throw new Error(`golden ausente: ${chave}`);
  return clonar(env);
}

/** Golden de uma ferramenta de diagnóstico no recorte mais próximo gravado. */
export function goldenAte(ferramenta: string, ateAnomes: number): Envelope {
  return golden(`${ferramenta}__ate_${ateAnomes >= ANOMES_FINAL ? ANOMES_FINAL : ANOMES_INICIAL}`);
}

export function resumoMes(anomes: number): Envelope | null {
  const env = GOLDENS.ferramentas[`resumo_mes__${anomes}`];
  return env ? clonar(env) : null;
}

export function trechosRag(ids: string[]): TrechoRag[] {
  return ids
    .map((id) => GOLDENS.rag_trechos.find((t) => t.trecho_id === id))
    .filter((t): t is TrechoRag => Boolean(t))
    .map(clonar);
}

export function erro(codigo: string, mensagem: string): ErroEnvelope {
  return { erro: { codigo, mensagem } };
}

function envelope(ferramenta: string, dados: Dados, ciclo: string, extra: Partial<Fonte> = {}): Envelope {
  return {
    dados,
    fonte: { ferramenta, tabelas: [], ...extra },
    avisos: [avisoSimulado(ciclo)],
  };
}

export function proximoAnomes(anomes: number): number {
  return anomes % 100 === 12 ? anomes + 89 : anomes + 1;
}

function mesesEntre(de: number, ate: number): number {
  return (Math.floor(ate / 100) - Math.floor(de / 100)) * 12 + ((ate % 100) - (de % 100));
}

// ---------------------------------------------------------------- 004

export interface ArgsObjetivo {
  tipo?: string;
  descricao?: string;
  valor_alvo?: number | null;
  prazo_meses?: number | null;
  prioridade?: string;
}

export function registrarObjetivo(args: ArgsObjetivo): Resultado {
  const valor = args.valor_alvo ?? null;
  const prazo = args.prazo_meses ?? null;
  if (valor !== null && !(valor > 0)) return erro("ENTRADA_INVALIDA", "valor_alvo deve ser positivo");
  if (prazo !== null && !(Number.isInteger(prazo) && prazo >= 1 && prazo <= 360)) {
    return erro("PRAZO_IMPLAUSIVEL", "prazo_meses fora de 1..360");
  }
  const objetivo = {
    tipo: args.tipo ?? "outro",
    descricao: args.descricao ?? "",
    valor_alvo: valor === null ? null : r2(valor),
    prazo_meses: prazo,
    prioridade: args.prioridade ?? "alta",
  };
  const faltando = [valor === null ? "valor_alvo" : null, prazo === null ? "prazo_meses" : null].filter(
    (c): c is string => c !== null,
  );
  return envelope("registrar_objetivo", { objetivo, faltando }, "004");
}

export const CENARIOS = ["conservador", "equilibrado", "acelerado"] as const;
export type NomeCenario = (typeof CENARIOS)[number];

export function escolherCenario(cenario: string): Resultado {
  if (!(CENARIOS as readonly string[]).includes(cenario)) return erro("ENTRADA_INVALIDA", "cenário desconhecido");
  return envelope("escolher_cenario", { cenario }, "004");
}

export interface Cenario {
  nome: string;
  aporte_mensal: number;
  prazo_meses: number;
  viavel: boolean;
  pct_capacidade: number;
}

export function cenarioDoGolden(nome: string, ateAnomes = ANOMES_INICIAL): Cenario | undefined {
  const cenarios = goldenAte("comparar_cenarios", ateAnomes).dados.cenarios as Cenario[];
  return cenarios.find((c) => c.nome === nome);
}

// ---------------------------------------------------------------- 005

export interface PedidoConsentimento {
  acao: string;
  resumo: string;
  o_que_faz: string;
  o_que_nao_faz: string;
  dados_usados: string;
}

export function solicitarConsentimento(consentId: string, pedido: PedidoConsentimento): Resultado {
  return envelope("solicitar_consentimento", { consent_id: consentId, status: "pendente", ...pedido }, "005");
}

export interface Plano {
  plano_id: string;
  cenario: string;
  valor_alvo: number;
  aporte_mensal: number;
  prazo_meses: number;
  criado_em_anomes: number;
}

export const PROXIMOS_PASSOS = [
  { texto: "Separar o aporte no início de cada mês, logo depois de receber." },
  { texto: "Montar uma reserva de emergência antes de acelerar (sugestão)." },
  { texto: "Ativar lembretes mensais", acao: "ativar_lembretes" },
  { texto: "Simular um financiamento", acao: "simular_contratacao" },
];

export function criarPlano(plano: Plano): Resultado {
  return envelope("criar_plano", { ...plano, proximos_passos: clonar(PROXIMOS_PASSOS) }, "005");
}

export function ativarLembretes(): Resultado {
  return envelope(
    "ativar_lembretes",
    {
      acao: "ativar_lembretes",
      status: "ok",
      mensagem: "Lembrete mensal ativado para o dia do seu aporte. Nenhum dinheiro foi movido.",
    },
    "005",
  );
}

export function simularContratacao(): Resultado {
  return envelope(
    "simular_contratacao",
    {
      acao: "simular_contratacao",
      status: "ok",
      mensagem:
        "Simulação genérica registrada, sem taxas e sem análise de crédito. Nada foi contratado; é só uma referência.",
    },
    "005",
  );
}

export function compartilharDados(): Resultado {
  return erro("NAO_PERMITIDO", "compartilhamento de dados não é permitido");
}

// ---------------------------------------------------------------- simular_objetivo (rotas)

function premissas(): Dados {
  return golden(`simular_objetivo__ate_${ANOMES_INICIAL}`).dados.premissas as Dados;
}

function capacidade(): number {
  return premissas().capacidade_mensal as number;
}

/** `simular_objetivo` com entradas sem golden: mesma regra do golden, rendimento 0 (spec, Q de rotas). */
export function simularObjetivo(
  valorAlvo: number,
  entrada: { prazo_meses: number } | { aporte_mensal: number },
  ateAnomes = ANOMES_INICIAL,
): Resultado {
  const cap = capacidade();
  let aporte: number;
  let prazo: number;
  let modo: string;
  if ("prazo_meses" in entrada) {
    if (!(Number.isInteger(entrada.prazo_meses) && entrada.prazo_meses >= 1 && entrada.prazo_meses <= 360)) {
      return erro("PRAZO_IMPLAUSIVEL", "prazo_meses fora de 1..360");
    }
    prazo = entrada.prazo_meses;
    aporte = r2(valorAlvo / prazo);
    modo = "prazo";
  } else {
    if (!(entrada.aporte_mensal > 0)) return erro("ENTRADA_INVALIDA", "aporte_mensal deve ser positivo");
    aporte = r2(entrada.aporte_mensal);
    prazo = Math.ceil(r2(valorAlvo / aporte));
    if (prazo > 360) return erro("PRAZO_IMPLAUSIVEL", "prazo acima de 360 meses");
    modo = "aporte";
  }
  const dados = {
    valor_alvo: r2(valorAlvo),
    aporte_mensal: aporte,
    prazo_meses: prazo,
    folga_mensal: r2(cap - aporte),
    viavel: aporte <= cap,
    modo,
    premissas: premissas(),
  };
  return {
    dados,
    fonte: { ferramenta: "simular_objetivo", tabelas: ["bussola_dados.perfil_mensal"], periodo: { inicio: 202501, fim: ateAnomes } },
    avisos: [avisoSimulado("004")],
  };
}

// ---------------------------------------------------------------- 006

export interface ResultadoMes {
  plano_id: string;
  anomes: number;
  planejado: number;
  realizado: number;
  desvio: number;
  status: "no_plano" | "desvio" | "folga";
  categoria_desvio: string | null;
}

export interface Rota {
  id: "A" | "B";
  titulo: string;
  descricao: string;
  aporte_mensal: number;
  prazo_meses: number;
  prazo_total_meses: number;
  simulacao: Envelope;
}

/** Média por macro de `resumo_mes` de jan/2025 até a criação do plano (mês ausente = 0). */
function mediaBase(criadoEm: number): Map<string, number> {
  const somas = new Map<string, number>();
  let n = 0;
  for (let m = 202501; m <= criadoEm; m = proximoAnomes(m)) {
    n += 1;
    const resumo = resumoMes(m);
    for (const g of (resumo?.dados.gastos_macro as { macro: string; total: number }[] | undefined) ?? []) {
      somas.set(g.macro, (somas.get(g.macro) ?? 0) + g.total);
    }
  }
  return new Map([...somas].map(([macro, soma]) => [macro, r2(soma / Math.max(n, 1))]));
}

function categoriaDesvio(resumo: Envelope, criadoEm: number): Dados | null {
  const base = mediaBase(criadoEm);
  let melhor: Dados | null = null;
  let maior = 0;
  for (const g of resumo.dados.gastos_macro as { macro: string; total: number }[]) {
    const media = base.get(g.macro) ?? 0;
    const aumento = r2(g.total - media);
    if (aumento > maior) {
      maior = aumento;
      melhor = { macro: g.macro, valor_mes: r2(g.total), media_base: media, aumento };
    }
  }
  return melhor;
}

function rotas(plano: Plano, restante: number, mesesRestantes: number, decorridos: number, ate: number): Rota[] {
  const saida: Rota[] = [];
  if (mesesRestantes > 0) {
    const a = simularObjetivo(restante, { prazo_meses: mesesRestantes }, ate);
    if (!ehErro(a)) {
      const aporte = a.dados.aporte_mensal as number;
      saida.push({
        id: "A",
        titulo: "Manter o prazo",
        descricao: `Aumentar o aporte para ${brl(aporte)} nos próximos ${meses(mesesRestantes)}.`,
        aporte_mensal: aporte,
        prazo_meses: mesesRestantes,
        prazo_total_meses: decorridos + mesesRestantes,
        simulacao: a,
      });
    }
  }
  const b = simularObjetivo(restante, { aporte_mensal: plano.aporte_mensal }, ate);
  if (!ehErro(b)) {
    const prazo = b.dados.prazo_meses as number;
    saida.push({
      id: "B",
      titulo: "Manter o aporte",
      descricao: `Seguir com ${brl(plano.aporte_mensal)} por mês e concluir em ${meses(prazo)}.`,
      aporte_mensal: plano.aporte_mensal,
      prazo_meses: prazo,
      prazo_total_meses: decorridos + prazo,
      simulacao: b,
    });
  }
  return saida;
}

/** Plano original (mês de criação e meta) mais o aporte vigente depois de ajustes. */
export interface PlanoVigente extends Plano {
  /** Mês em que o primeiro plano do objetivo foi criado (base da média e do prazo). */
  inicio_anomes: number;
}

export interface SaidaAvancarMes {
  resultado: Resultado;
  registro?: ResultadoMes;
}

export function avancarMes(plano: PlanoVigente | null, ateAnomes: number, historico: ResultadoMes[]): SaidaAvancarMes {
  if (!plano) return { resultado: erro("SEM_PLANO_ATIVO", "nenhum plano ativo") };
  if (ateAnomes >= ANOMES_FINAL) return { resultado: erro("FIM_DO_REPLAY", `replay terminou em ${ANOMES_FINAL}`) };
  const anomes = proximoAnomes(ateAnomes);
  const resumo = resumoMes(anomes);
  if (!resumo) return { resultado: erro("INDISPONIVEL", "resumo do mês ausente") };

  const planejado = r2(plano.aporte_mensal);
  const realizado = r2(resumo.dados.sobra as number);
  const desvio = r2(realizado - planejado);
  const tolerancia = r2(planejado * TOLERANCIA);
  const status = desvio < -tolerancia ? "desvio" : desvio > tolerancia ? "folga" : "no_plano";
  const categoria = status === "desvio" ? categoriaDesvio(resumo, plano.inicio_anomes) : null;

  const acumulado = r2(
    [...historico.map((h) => h.realizado), realizado].filter((v) => v > 0).reduce((s, v) => s + v, 0),
  );
  const restante = r2(Math.max(plano.valor_alvo - acumulado, 0));
  const decorridos = mesesEntre(plano.inicio_anomes, anomes);
  const mesesRestantes = Math.max(plano.prazo_meses - decorridos, 0);
  const percentual = r2((acumulado / plano.valor_alvo) * 100);

  const dados: Dados = {
    plano_id: plano.plano_id,
    anomes,
    planejado,
    realizado,
    desvio,
    tolerancia,
    status,
    categoria_desvio: categoria,
    acumulado,
    percentual,
    restante,
    meses_decorridos: decorridos,
    meses_restantes: mesesRestantes,
    resumo_mes: resumo,
    rotas: status === "desvio" ? rotas(plano, restante, mesesRestantes, decorridos, anomes) : [],
  };
  const resultado: Envelope = {
    dados,
    fonte: { ferramenta: "avancar_mes", tabelas: resumo.fonte.tabelas, periodo: { inicio: anomes, fim: anomes } },
    avisos: [avisoSimulado("006")],
  };
  const registro: ResultadoMes = {
    plano_id: plano.plano_id,
    anomes,
    planejado,
    realizado,
    desvio,
    status,
    categoria_desvio: (categoria?.macro as string | undefined) ?? null,
  };
  return { resultado, registro };
}

export function ajustarPlano(planoId: string, rota: Rota): Resultado {
  return envelope(
    "ajustar_plano",
    {
      plano_id: planoId,
      rota: rota.id,
      aporte_mensal: rota.aporte_mensal,
      prazo_meses: rota.prazo_total_meses,
      mensagem: `Plano ajustado: ${brl(rota.aporte_mensal)} por mês, ${meses(rota.prazo_meses)} até a meta.`,
    },
    "006",
  );
}

export function statusPlano(
  plano: PlanoVigente | null,
  objetivo: Dados | null,
  historico: ResultadoMes[],
): Resultado {
  if (!plano) return erro("SEM_PLANO_ATIVO", "nenhum plano ativo");
  const acumulado = r2(historico.map((h) => h.realizado).filter((v) => v > 0).reduce((s, v) => s + v, 0));
  const ultimo = historico.at(-1);
  const decorridos = ultimo ? mesesEntre(plano.inicio_anomes, ultimo.anomes) : 0;
  return {
    dados: {
      objetivo,
      plano,
      meses_decorridos: decorridos,
      acumulado,
      percentual: r2((acumulado / plano.valor_alvo) * 100),
      restante: r2(Math.max(plano.valor_alvo - acumulado, 0)),
      ultimo_status: ultimo?.status ?? null,
      historico: clonar(historico),
    },
    fonte: {
      ferramenta: "status_plano",
      tabelas: [],
      periodo: ultimo ? { inicio: proximoAnomes(plano.inicio_anomes), fim: ultimo.anomes } : null,
    },
    avisos: [avisoSimulado("006")],
  };
}

/** Período de dados usado no pedido de consentimento (`jan–jun/2025`). */
export function periodoDados(ateAnomes: number): string {
  return periodo({ inicio: 202501, fim: ateAnomes });
}
