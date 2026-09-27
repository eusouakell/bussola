// Chips do composer: respostas rápidas do turno atual ou sugestões da etapa.
import type { Modo } from "../agente/transporte";
import { motivoSemAvanco } from "./avanco";
import type { ModeloSessao } from "./modelo";
import { SUGESTOES_POR_ESTADO, TEXTO_AVANCAR } from "./sugestoes-padrao";

/**
 * Sugestões da etapa quando o agente não propôs nenhuma. Só no modo simulado:
 * `SUGESTOES_POR_ESTADO` é o roteiro do fake, e oferecê-lo ao vivo mostrava ao
 * cliente chips que o agente real nunca propôs (A4 da varredura).
 */
export function sugestoesDoComposer(modelo: ModeloSessao, modo: Modo): string[] {
  const { itens, estado } = modelo;
  if (!itens.some((i) => i.tipo === "mensagem_cliente")) return [];
  const semAvanco = motivoSemAvanco(estado) !== null;
  const filtrar = (lista: string[]) =>
    semAvanco ? lista.filter((s) => s.toLocaleLowerCase("pt-BR") !== TEXTO_AVANCAR) : lista;

  for (let i = itens.length - 1; i >= 0; i -= 1) {
    const item = itens[i];
    if (item.tipo === "mensagem_cliente") break;
    // O bloqueio traz as próprias respostas rápidas.
    if (item.tipo === "guardrail") return [];
    if (item.tipo === "mensagem_agente" && item.respostasRapidas?.length) return filtrar(item.respostasRapidas);
  }
  // Autorização pendente se responde no próprio card.
  if (Object.values(estado.consentimentos ?? {}).some((c) => c.status === "pendente")) return [];
  if (modo !== "simulado" || !estado.estado_jornada) return [];
  return filtrar(SUGESTOES_POR_ESTADO[estado.estado_jornada]);
}
