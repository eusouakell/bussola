// Copy do agente simulado (pt-BR, docs/design/prompt-claude-design-chat.md §6–7).
// Só cita números que vieram das ferramentas; nunca calcula (constituição III).
// Proibido: "garantido", "aprovado", "contrate agora" e urgência artificial.
import type { EstadoJornada } from "../agente/tipos";
import { brl, meses, mesExtenso, percentual, periodo } from "../formatacao/formatar";
import type { TipoObjetivo } from "./intencoes";

// Os rótulos das sugestões e dos CTAs são da aplicação, não do fake: os dois
// modos os usam. Moram em `sessao/sugestoes-padrao.ts` e o simulado os
// reexporta para seguir usando `T.R_*` (a direção é simulado → sessao, R3).
export {
  R_ACELERADO,
  R_AJUDA,
  R_AVANCAR,
  R_CAMINHOS,
  R_CONTINUAR,
  R_FINANCIAMENTO,
  R_LEMBRETES,
  R_MANTER,
  R_NAO,
  R_OUTRO_CAMINHO,
  R_SIM,
  R_STATUS,
  R_VALORES_DEMO,
  SUGESTOES_INICIAIS,
  SUGESTOES_POR_ESTADO,
} from "../sessao/sugestoes-padrao";

export const SAUDACAO = "Oi, Fernando! Eu sou a Bússola, seu assistente financeiro. Qual objetivo você quer tirar do papel?";

export const OBJETIVOS: Record<Exclude<TipoObjetivo, "dividas">, { descricao: string; frase: string }> = {
  imovel: { descricao: "Primeiro apartamento", frase: "seu primeiro apartamento" },
  viagem: { descricao: "Viagem no ano que vem", frase: "a sua viagem" },
  educacao: { descricao: "Pós-graduação", frase: "a sua pós" },
};

export function perguntaValores(frase: string): string {
  return `Ótimo objetivo! Anotei ${frase}, com prioridade alta. Pra eu calcular certinho: quanto você quer juntar de entrada, e em quanto tempo?`;
}

export const SEM_VALOR =
  "Sem problema. Para a demonstração, posso usar uma entrada de R$ 30 mil em 2 anos como referência, e você ajusta depois. Pode ser?";

export const SO_VALOR = "Anotei o valor. E em quanto tempo você quer chegar lá?";

/** Linha secundária, dita uma única vez: a simulação detalhada é a da demonstração. */
export const AVISO_SIMULACAO_GRAVADA =
  "Nesta demonstração, a simulação detalhada está gravada para R$ 30 mil em 24 meses.";

interface MetaForaDoPerfil {
  descricao: string;
  valor_alvo: number;
  prazo_meses: number;
  aporte_necessario: number;
  sobra_mediana: number;
  meta_intermediaria: number;
}

/**
 * BUG-03: meta acima do perfil. Reconhece o objetivo, mostra os números do
 * cliente e propõe uma primeira etapa. `tentativa` muda o texto quando ele
 * insiste: o sonho vira destino final e a meta possível vira degrau.
 */
export function metaForaDoPerfil(d: MetaForaDoPerfil, tentativa: number): string {
  const conta = `${brl(d.valor_alvo)} em ${meses(d.prazo_meses)} pedem ${brl(d.aporte_necessario)} por mês, e o que costuma sobrar no seu mês é ${brl(d.sobra_mediana)}`;
  const etapa = `${brl(d.meta_intermediaria)} em ${meses(d.prazo_meses)}`;
  if (tentativa <= 1) {
    return `Anotei o seu objetivo: ${d.descricao}, ${brl(d.valor_alvo)} em ${meses(d.prazo_meses)}. O plano para chegar nesse tamanho é complexo: ${conta}. Minha sugestão é focar primeiro numa meta que cabe no seu perfil, de ${etapa}. Depois dela, a gente aumenta o objetivo e chega mais perto do seu sonho — assim você tem mais chance de avançar de verdade.`;
  }
  const variantes = [
    `Seu destino final continua anotado: ${d.descricao}, ${brl(d.valor_alvo)}. A conta é que não fecha hoje: ${conta}. Então vamos por etapas, e a primeira é ${etapa}, no seu ritmo. Com ela de pé, subimos o objetivo um degrau, e depois outro, até chegar perto do que você quer.`,
    `Entendo a vontade, e ela segue no mapa como destino final. Só que os números do seu mês são estes: ${conta}. Por isso eu insisto na primeira etapa de ${etapa}: é dela que sai o próximo degrau em direção ao seu objetivo maior.`,
  ];
  return variantes[(tentativa - 2) % variantes.length];
}

/** BUG-02: assunto fora do escopo, com resposta que escalona a cada turno seguido. */
export const FORA_DO_ESCOPO_1 =
  "Essa eu não sei responder. Eu cuido do seu objetivo financeiro: monto um plano, comparo caminhos e acompanho mês a mês. Por onde você quer começar?";

const FORA_DO_ESCOPO_2: Record<EstadoJornada, string> = {
  OBJETIVO:
    "Continuo fora do meu assunto, então deixo o convite mais direto: me diga o que você quer conquistar — um apartamento, uma viagem, uma pós — ou peça para eu olhar suas dívidas.",
  ENTENDER:
    "Esse tema não é meu. O que eu preciso de você é o tamanho da meta e o prazo, por exemplo R$ 30 mil em 2 anos. Com isso eu já monto a conta.",
  ANTECIPAR:
    "Isso foge do que eu faço. Daqui, o que ajuda é ver os caminhos possíveis para a sua meta, ou você me dizer quanto consegue guardar por mês.",
  ORIENTAR:
    "Esse assunto não é comigo. Do que está na mesa, eu posso seguir com um dos caminhos que te mostrei ou desenhar outro com o valor que couber no seu mês.",
  AGIR: "Fora do meu assunto de novo. O que eu tenho para agora é avançar um mês do seu plano ou ativar os lembretes mensais.",
  ACOMPANHAR: "Isso eu não cubro. No seu plano, eu posso avançar mais um mês ou mostrar o status do que você já acumulou.",
};

export function foraDoEscopo2(estado: EstadoJornada): string {
  return FORA_DO_ESCOPO_2[estado];
}

const FORA_DO_ESCOPO_FINAL = [
  "Vou ficar no que faço bem, que é o seu plano. Para outros assuntos, o app do banco tem os canais de atendimento. Quando quiser, é só me dizer o seu objetivo.",
  "Sigo por aqui, à sua disposição para o seu plano. Os outros temas ficam melhor com o atendimento do app do banco. Quando você quiser retomar a meta, eu continuo aqui.",
];

/** Terceira vez em diante: encerra o assunto e aponta o atendimento humano, sem repetir a frase. */
export function foraDoEscopoFinal(vez: number): string {
  return FORA_DO_ESCOPO_FINAL[(vez - 3) % FORA_DO_ESCOPO_FINAL.length];
}

export const DUVIDA_CREDITO =
  "Sobre crédito eu não negocio nem antecipo condições: taxa, prazo e limite saem da análise do banco. O que eu consigo fazer é simular um financiamento genérico, sem taxas, só como referência. Quer que eu faça isso?";

export function diagnostico(d: {
  periodo: { inicio: number; fim: number };
  renda_media?: number;
  sobra_mediana?: number;
  comprometimento?: number;
  e4: boolean;
  e3: boolean;
}): string {
  const partes = [`Olhei seu extrato de ${periodo(d.periodo)}.`];
  if (typeof d.renda_media === "number") partes.push(`Sua renda média é de ${brl(d.renda_media)}.`);
  if (d.e4) {
    partes.push("Tenho poucos meses de histórico para estimar sua sobra com segurança, então trate a simulação como uma referência.");
  } else if (typeof d.sobra_mediana === "number") {
    partes.push(`Na mediana, sobram ${brl(d.sobra_mediana)} por mês.`);
  }
  if (typeof d.comprometimento === "number") {
    partes.push(`Suas parcelas comprometem ${percentual(d.comprometimento)} da renda.`);
  }
  if (d.e3) partes.push("Não consegui consultar as oportunidades de corte agora; sigo com o que tenho.");
  return partes.join(" ");
}

export function simulacao(d: { valor_alvo: number; prazo_meses: number; aporte_mensal: number; folga_mensal: number; viavel: boolean }): string {
  const base = `Para juntar ${brl(d.valor_alvo)} em ${meses(d.prazo_meses)}, o aporte seria de ${brl(d.aporte_mensal)} por mês`;
  return d.viavel
    ? `${base}, e ainda ficaria uma folga de ${brl(d.folga_mensal)}. Quer ver os caminhos possíveis?`
    : `${base}, acima do que costuma sobrar. Quer ver os caminhos possíveis?`;
}

export function aporteLivre(d: { aporte_mensal: number; valor_alvo: number; prazo_meses: number; viavel: boolean; capacidade: number }): string {
  const base = `Guardando ${brl(d.aporte_mensal)} por mês, você chega aos ${brl(d.valor_alvo)} em ${meses(d.prazo_meses)}.`;
  return d.viavel
    ? `${base} Cabe na sua sobra mediana de ${brl(d.capacidade)}.`
    : `${base} Esse aporte passa da sua sobra mediana de ${brl(d.capacidade)}, então fica apertado.`;
}

export const OUTRO_CAMINHO =
  "Me conta do seu jeito quanto você consegue guardar por mês. Por exemplo: “e se eu guardar R$ 2.000 por mês?”";

export function comparacao(d: {
  prazo_objetivo: number;
  recomendado: { nome: string; aporte_mensal: number; prazo_meses: number } | null;
  fora: { nome: string; prazo_meses: number }[];
}): string {
  if (!d.recomendado) {
    return `Montei três caminhos com a sua sobra. Nenhum deles cabe em ${meses(d.prazo_objetivo)}; dá para alongar o prazo ou rever a meta.`;
  }
  const r = d.recomendado;
  const fora = d.fora.map((c) => `${c.nome}: ${meses(c.prazo_meses)}`).join("; ");
  const frase = `Montei três caminhos com a sua sobra. Recomendo o ${r.nome}: ${brl(r.aporte_mensal)} por mês, com a meta atingida em ${meses(r.prazo_meses)}, dentro do seu prazo de ${meses(d.prazo_objetivo)}.`;
  return fora ? `${frase} Os outros passam do prazo (${fora}).` : frase;
}

export function escolha(nome: string, viavel: boolean): string {
  const aviso = viavel ? "" : " Esse caminho passa do seu prazo, mas posso seguir com ele.";
  return `Boa escolha: caminho ${nome}.${aviso} Antes de criar o plano, preciso da sua autorização.`;
}

export function pedidoPlano(d: { aporte_mensal: number; prazo_meses: number; valor_alvo: number; periodo: string; descricao: string }) {
  return {
    acao: "criar_plano",
    resumo: `Criar seu plano “${d.descricao}”`,
    o_que_faz: `Registrar o plano (${brl(d.aporte_mensal)}/mês por ${meses(d.prazo_meses)}, meta de ${brl(d.valor_alvo)}) e acompanhar seu progresso mês a mês.`,
    o_que_nao_faz: "Mover dinheiro, contratar produtos ou compartilhar seus dados.",
    dados_usados: `Seu extrato de ${d.periodo}.`,
  };
}

export function pedidoAjuste(d: { rota: string; titulo: string; aporte_mensal: number; prazo_meses: number }) {
  return {
    acao: "ajustar_plano",
    resumo: `Adotar a rota ${d.rota}: ${d.titulo.toLowerCase()}`,
    o_que_faz: `Ajustar o plano para ${brl(d.aporte_mensal)}/mês, com ${meses(d.prazo_meses)} até a meta.`,
    o_que_nao_faz: "Mover dinheiro, contratar produtos ou compartilhar seus dados.",
    dados_usados: "O resultado do mês e o seu plano atual.",
  };
}

export const PEDIDO_LEMBRETES = {
  acao: "ativar_lembretes",
  resumo: "Ativar lembretes mensais",
  o_que_faz: "Enviar um lembrete por mês, no dia do seu aporte.",
  o_que_nao_faz: "Mover dinheiro, contratar produtos ou compartilhar seus dados.",
  dados_usados: "O valor e a data do aporte do seu plano.",
};

export const PEDIDO_FINANCIAMENTO = {
  acao: "simular_contratacao",
  resumo: "Simular um financiamento genérico",
  o_que_faz: "Registrar uma simulação genérica de financiamento, sem taxas, só como referência.",
  o_que_nao_faz: "Contratar crédito, consultar seu CPF ou compartilhar seus dados.",
  dados_usados: "O valor da meta do seu plano.",
};

export const PRECISO_AUTORIZACAO = "Essa ação precisa da sua autorização. Confira o que vou e o que não vou fazer.";

export function planoCriado(d: { aporte_mensal: number; prazo_meses: number }): string {
  return `Pronto, seu plano está criado: ${brl(d.aporte_mensal)} por mês por ${meses(d.prazo_meses)}. Quando quiser, use “Avançar um mês” para ver como o próximo mês foi.`;
}

export const RECUSA_RESPEITOSA =
  "Tudo bem, não fiz nada. Sua decisão fica registrada e você pode mudar de ideia quando quiser.";

export const CONFIRMAR = "Só para confirmar: posso seguir com essa ação? Responda sim ou não.";

export function mesDesvio(d: {
  anomes: number;
  realizado: number;
  planejado: number;
  desvio: number;
  macro?: string;
  valor_mes?: number;
  media_base?: number;
}): string {
  const causa =
    d.macro && typeof d.valor_mes === "number"
      ? ` O que mais pesou foi ${d.macro}: ${brl(d.valor_mes)} no mês, contra uma média de ${brl(d.media_base)}.`
      : "";
  return `Em ${mesExtenso(d.anomes)} sobraram ${brl(d.realizado)}, abaixo do planejado de ${brl(d.planejado)} (desvio de ${brl(d.desvio)}).${causa} Recalculei duas rotas para você voltar ao plano.`;
}

export function mesFolga(d: { anomes: number; realizado: number; planejado: number; acumulado: number; percentual: number }): string {
  return `Em ${mesExtenso(d.anomes)} sobraram ${brl(d.realizado)}, acima do planejado de ${brl(d.planejado)}. Você já acumulou ${brl(d.acumulado)}, ${percentual(d.percentual)} da meta.`;
}

export function mesNoPlano(d: { anomes: number; realizado: number; acumulado: number; percentual: number }): string {
  return `Em ${mesExtenso(d.anomes)} você ficou dentro do plano, com ${brl(d.realizado)} guardados. Já são ${brl(d.acumulado)}, ${percentual(d.percentual)} da meta.`;
}

export const SEM_PLANO = "Para acompanhar mês a mês, primeiro precisamos criar o seu plano.";
export const FIM_REPLAY = "Chegamos ao fim da demonstração: os dados vão até dezembro de 2025.";

export function planoAjustado(d: { aporte_mensal: number; prazo_meses: number }): string {
  return `Plano ajustado. A partir de agora, o aporte é de ${brl(d.aporte_mensal)} por mês, com ${meses(d.prazo_meses)} até a meta.`;
}

export const QUAL_ROTA = "Qual rota você quer adotar?";
export const SEM_ROTA = "Ainda não há uma rota recalculada. Avance um mês para ver se o plano precisa de ajuste.";
export const LEMBRETES_OK = "Lembretes ativados. Vou te avisar uma vez por mês, no dia do seu aporte.";
export const FINANCIAMENTO_OK =
  "Registrei uma simulação genérica, sem taxas, só como referência. Nada foi contratado e nenhuma análise de crédito foi feita.";
export const STATUS = "Aqui está o resumo do seu plano até agora.";
export const MANTER = "Combinado, o plano segue igual.";
export const DIVIDAS_INTRO = "Vamos olhar suas parcelas e o quanto elas pesam na renda.";

export function dividas(d: { comprometimento: number; juros: number }): string {
  return `Hoje suas parcelas comprometem ${percentual(d.comprometimento)} da renda, e os juros pagos ficam em média em ${brl(d.juros)} por mês. Quer transformar isso num objetivo? Dá para planejar uma entrada e acompanhar mês a mês.`;
}

export function retryOk(nome: string): string {
  return `Agora consegui consultar ${nome}.`;
}

export const REDIAGNOSTICO = "Refiz seu diagnóstico com os dados disponíveis.";

export const AJUDA =
  "Posso te ajudar a planejar um objetivo, comparar caminhos, criar um plano com a sua autorização e acompanhar mês a mês. Não movo dinheiro nem contrato produtos.";

export const NAO_ENTENDI = "Não entendi bem. Posso te ajudar com o seu objetivo, os caminhos ou o acompanhamento do plano.";
