// Regra "pode avançar o mês?". Morava em `componentes/layout/BarraDemo.tsx`, o
// que fazia `sessao/` importar um componente React (ciclo da varredura, R3).
import type { EstadoSessao } from "../agente/tipos";
import { CONFIG } from "../config";
import { mesAbrev } from "../formatacao/formatar";

/** Motivo para o botão ficar desabilitado, ou `null` quando pode avançar. */
export function motivoSemAvanco(estado: EstadoSessao): string | null {
  if (!estado.plano_id) return "Crie o plano para acompanhar mês a mês.";
  if ((estado.ate_anomes ?? CONFIG.anomesInicial) >= CONFIG.anomesFinal) {
    return `Os dados da demonstração vão até ${mesAbrev(CONFIG.anomesFinal)}.`;
  }
  return null;
}
