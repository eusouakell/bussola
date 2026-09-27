// Rótulos das sugestões e dos CTAs da aplicação, em pt-BR. Ficam aqui, e não
// em `simulado/textos.ts`, porque os dois modos precisam deles: os botões das
// vistas e a tela de boas-vindas existem com o agente real ou com o simulado.
// A direção é sempre `simulado/` → `sessao/`, nunca o contrário (R3).
//
// São frases que o cliente *envia*, então o agente (real ou simulado) precisa
// entendê-las: mudar o texto muda o que chega ao agente.
import type { EstadoJornada } from "../agente/tipos";

/** Objetivos oferecidos na tela de boas-vindas (`BoasVindas.tsx`). */
export const SUGESTOES_INICIAIS = [
  "Quero comprar meu primeiro apartamento",
  "Quero viajar no ano que vem",
  "Quero fazer uma pós",
  "Quero organizar minhas dívidas",
];

export const R_VALORES_DEMO = "R$ 30 mil em 2 anos";
export const R_CAMINHOS = "Me mostra os caminhos";
export const R_ACELERADO = "Quero o caminho acelerado";
export const R_OUTRO_CAMINHO = "Outro caminho";
export const R_AVANCAR = "Avançar um mês";
export const R_STATUS = "Ver status do plano";
export const R_MANTER = "Manter o plano";
export const R_LEMBRETES = "Ativar lembretes mensais";
export const R_FINANCIAMENTO = "Simular um financiamento";
export const R_CONTINUAR = "Continuar o plano";
export const R_SIM = "Sim, autorizo";
export const R_NAO = "Agora não";
export const R_AJUDA = "O que você pode fazer?";
/** Texto enviado pelo botão "Avançar um mês" da barra do apresentador, normalizado. */
export const TEXTO_AVANCAR = "avançar um mês";

/**
 * Chips sugeridos por etapa da jornada. É o roteiro do agente **simulado**: o
 * agente ao vivo propõe as próprias respostas rápidas, então `sugestoes.ts` só
 * usa este mapa no modo simulado (A4 da varredura).
 */
export const SUGESTOES_POR_ESTADO: Record<EstadoJornada, string[]> = {
  OBJETIVO: SUGESTOES_INICIAIS,
  ENTENDER: [R_VALORES_DEMO],
  ANTECIPAR: [R_CAMINHOS],
  ORIENTAR: [R_ACELERADO, R_OUTRO_CAMINHO],
  AGIR: [R_AVANCAR, R_LEMBRETES],
  ACOMPANHAR: [R_AVANCAR, R_STATUS],
};
