// Leitura das vistas P1–P5 (FR-024): tudo vem de `modelo.estado` e das
// respostas de ferramentas já recebidas em `modelo.itens`. Nada é calculado
// aqui (FR-007): as funções só escolhem qual resposta ler e devolvem o valor
// junto com a resposta de origem, para o `ChipFonte`.
import { dadosDe } from "../agente/envelope";
import type { Consentimento, Dados, RespostaFerramenta } from "../agente/tipos";
import { lista, num, obj, txt } from "../componentes/cards/ler";
import type { ModeloSessao } from "../sessao/modelo";

/** Resposta bem-sucedida de uma chamada de ferramenta, na ordem da conversa. */
export interface Resposta {
  nome: string;
  chamadaId: string;
  resposta: RespostaFerramenta;
  /** Posição do item na conversa (só para ordenar). */
  ordem: number;
}

/** Valor lido de uma resposta, com a origem para o chip de fonte. */
export interface Lido {
  valor: number | undefined;
  origem: Resposta | undefined;
}

/**
 * Todas as respostas sem erro, uma por chamada. Vem do item de ferramenta
 * (inclui `escolher_cenario`, que não gera card) e, na falta dele, do card.
 */
export function respostas(modelo: ModeloSessao): Resposta[] {
  const vistas = new Set<string>();
  const saida: Resposta[] = [];
  modelo.itens.forEach((item, ordem) => {
    let r: Resposta | undefined;
    if (item.tipo === "ferramenta" && item.status === "ok" && item.resposta) {
      r = { nome: item.nome, chamadaId: item.chamadaId, resposta: item.resposta, ordem };
    } else if (item.tipo === "card") {
      r = { nome: item.nome, chamadaId: item.chamadaId, resposta: item.resposta, ordem };
    }
    if (!r || r.resposta.tipo === "erro" || vistas.has(r.chamadaId)) return;
    vistas.add(r.chamadaId);
    saida.push(r);
  });
  return saida;
}

function dePlano(r: Resposta): Dados | undefined {
  return r.nome === "status_plano" ? obj(dadosDe(r.resposta), "plano") : dadosDe(r.resposta);
}

/** Último valor de `chave` entre as respostas das ferramentas indicadas. */
function ultimoCom(rs: Resposta[], nomes: string[], chave: string): Lido {
  for (let i = rs.length - 1; i >= 0; i -= 1) {
    const r = rs[i];
    if (!nomes.includes(r.nome)) continue;
    const valor = num(dePlano(r), chave);
    if (valor !== undefined) return { valor, origem: r };
  }
  return { valor: undefined, origem: undefined };
}

function ultima(rs: Resposta[], nomes: string[], depoisDe = -1): Resposta | undefined {
  for (let i = rs.length - 1; i >= 0; i -= 1) {
    if (rs[i].ordem <= depoisDe) return undefined;
    if (nomes.includes(rs[i].nome)) return rs[i];
  }
  return undefined;
}

export type StatusMes = "no_plano" | "desvio" | "folga";

export function statusMes(valor: string | undefined): StatusMes | undefined {
  return valor === "no_plano" || valor === "desvio" || valor === "folga" ? valor : undefined;
}

/** Um mês de acompanhamento (`avancar_mes`) ou uma linha do histórico do `status_plano`. */
export interface MesLido {
  chave: string;
  dados: Dados;
  origem: Resposta;
}

/** Evento da trilha: criação, ajuste ou mês acompanhado, na ordem da conversa. */
export type EventoTrilha =
  | { tipo: "criacao"; origem: Resposta }
  | { tipo: "ajuste"; origem: Resposta }
  | { tipo: "mes"; mes: MesLido };

export interface PlanoLido {
  planoId: string;
  descricao: string | undefined;
  /** Caminho escolhido: `criar_plano.cenario`, senão `escolher_cenario`. */
  cenario: string | undefined;
  origemCenario: Resposta | undefined;
  criacao: Resposta | undefined;
  ajuste: Resposta | undefined;
  meta: Lido;
  aporte: Lido;
  prazo: Lido;
  criadoEm: Lido;
  /** Última leitura de progresso (`status_plano` ou `avancar_mes`) do plano atual. */
  progresso: Resposta | undefined;
  /** Status do último mês acompanhado, lido da resposta de progresso. */
  ultimoStatus: StatusMes | undefined;
  /** Último mês acompanhado (`avancar_mes`), se a leitura de progresso for um mês. */
  ultimoMes: Resposta | undefined;
  trilha: EventoTrilha[];
  simulacao: Resposta | undefined;
  comparacao: Resposta | undefined;
  lembretes: Consentimento | undefined;
  /** `session.state.consentimentos`, por ação. */
  consentimentos: Record<string, Consentimento>;
  todas: Resposta[];
}

const PLANO = ["criar_plano", "ajustar_plano", "status_plano"];

export function lerPlano(modelo: ModeloSessao): PlanoLido | null {
  const planoId = modelo.estado.plano_id;
  if (!planoId) return null;
  const rs = respostas(modelo);
  const criacao = ultima(rs, ["criar_plano"]);
  const inicio = criacao?.ordem ?? -1;
  const ajuste = ultima(rs, ["ajustar_plano"], inicio);
  const progresso = ultima(rs, ["status_plano", "avancar_mes"], inicio);
  const escolha = ultima(rs, ["escolher_cenario"]);

  const cenarioCriacao = txt(dadosDe(criacao?.resposta), "cenario");
  const cenarioEscolha = txt(dadosDe(escolha?.resposta), "cenario");
  const cenarioEstado = typeof modelo.estado.cenario_escolhido === "string" ? modelo.estado.cenario_escolhido : undefined;

  const dadosProgresso = dadosDe(progresso?.resposta);
  const ultimoStatus =
    progresso?.nome === "avancar_mes" ? statusMes(txt(dadosProgresso, "status")) : statusMes(txt(dadosProgresso, "ultimo_status"));

  const meses: EventoTrilha[] = [];
  for (const r of rs) {
    if (r.ordem < inicio) continue;
    if (r.nome === "criar_plano") meses.push({ tipo: "criacao", origem: r });
    else if (r.nome === "ajustar_plano") meses.push({ tipo: "ajuste", origem: r });
    else if (r.nome === "avancar_mes") meses.push({ tipo: "mes", mes: { chave: r.chamadaId, dados: dadosDe(r.resposta), origem: r } });
  }
  // Sem meses de `avancar_mes` na conversa: usa o histórico do último status.
  if (!meses.some((e) => e.tipo === "mes") && progresso?.nome === "status_plano") {
    lista(dadosProgresso, "historico").forEach((h, i) => {
      meses.push({ tipo: "mes", mes: { chave: `${progresso.chamadaId}-${i}`, dados: h, origem: progresso } });
    });
  }

  return {
    planoId,
    descricao: modelo.estado.objetivo?.descricao || undefined,
    cenario: cenarioCriacao ?? cenarioEscolha ?? cenarioEstado,
    origemCenario: cenarioCriacao ? criacao : cenarioEscolha ? escolha : undefined,
    criacao,
    ajuste,
    meta: ultimoCom(rs, ["criar_plano", "status_plano"], "valor_alvo"),
    aporte: ultimoCom(rs, PLANO, "aporte_mensal"),
    prazo: ultimoCom(rs, PLANO, "prazo_meses"),
    criadoEm: ultimoCom(rs, ["criar_plano", "status_plano"], "criado_em_anomes"),
    progresso,
    ultimoStatus,
    ultimoMes: progresso?.nome === "avancar_mes" ? progresso : undefined,
    trilha: meses,
    simulacao: ultima(rs, ["simular_objetivo"]),
    comparacao: ultima(rs, ["comparar_cenarios"]),
    lembretes: modelo.estado.consentimentos?.ativar_lembretes,
    consentimentos: modelo.estado.consentimentos ?? {},
    todas: rs,
  };
}

/** Número da resposta de progresso (`acumulado`, `percentual`, `restante`, `meses_decorridos`). */
export function doProgresso(plano: PlanoLido, chave: string): Lido {
  const valor = num(dadosDe(plano.progresso?.resposta), chave);
  return { valor, origem: valor === undefined ? undefined : plano.progresso };
}

/** Cenário escolhido dentro da última comparação (só leitura por nome). */
export function cenarioComparado(plano: PlanoLido): Dados | undefined {
  if (!plano.cenario) return undefined;
  return lista(dadosDe(plano.comparacao?.resposta), "cenarios").find((c) => txt(c, "nome") === plano.cenario);
}

/** Uma resposta por ferramenta (a mais recente), na ordem da primeira chamada. */
export function fontesUsadas(rs: Resposta[]): Resposta[] {
  const porNome = new Map<string, Resposta>();
  for (const r of rs) {
    if (r.resposta.tipo !== "envelope") continue;
    porNome.delete(r.nome);
    porNome.set(r.nome, r);
  }
  const primeira = new Map<string, number>();
  for (const r of rs) if (!primeira.has(r.nome)) primeira.set(r.nome, r.ordem);
  return [...porNome.values()].sort((a, b) => (primeira.get(a.nome) ?? 0) - (primeira.get(b.nome) ?? 0));
}
