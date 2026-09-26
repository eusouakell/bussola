// Chips do composer: respostas rápidas do turno atual ou sugestões da etapa.
import { motivoSemAvanco, TEXTO_AVANCAR } from "../componentes/layout/BarraDemo";
import { SUGESTOES_POR_ESTADO } from "../simulado/textos";
import type { ModeloSessao } from "./modelo";

export function sugestoesDoComposer(modelo: ModeloSessao): string[] {
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
  return estado.estado_jornada ? filtrar(SUGESTOES_POR_ESTADO[estado.estado_jornada]) : [];
}
