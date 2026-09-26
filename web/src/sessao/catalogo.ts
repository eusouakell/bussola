// Mapeamento ferramenta → UI (plan.md, "Mapeamento ferramenta → UI") e copy
// de erro por código (contracts/eventos-agente.md §4).
import type { TagMensagem } from "../agente/tipos";

interface EntradaCatalogo {
  legivel: string;
  tag?: TagMensagem;
  /** Nome do componente de card; ausente = só linha e Bastidores. */
  card?: string;
}

export const CATALOGO: Record<string, EntradaCatalogo> = {
  perfil_financeiro: { legivel: "Perfil financeiro", tag: "diagnostico", card: "CardDiagnostico" },
  capacidade_poupanca: { legivel: "Capacidade de poupança", tag: "diagnostico", card: "CardDiagnostico" },
  dividas_e_parcelas: { legivel: "Dívidas e parcelas", tag: "diagnostico", card: "CardDividas" },
  oportunidades_corte: { legivel: "Oportunidades de corte", tag: "diagnostico", card: "CardOportunidadesCorte" },
  resumo_mes: { legivel: "Resumo do mês", tag: "diagnostico" },
  referencia_coorte: { legivel: "Referência de pessoas parecidas", tag: "diagnostico" },
  simular_objetivo: { legivel: "Simulação do objetivo", tag: "simulacao", card: "CardSimulacao" },
  comparar_cenarios: { legivel: "Comparação de cenários", tag: "recomendacao", card: "ComparadorCenarios" },
  buscar_contexto_financeiro: {
    legivel: "Base de conhecimento",
    tag: "recomendacao",
    card: "ExplicacaoRecomendacao",
  },
  registrar_objetivo: { legivel: "Registro do objetivo", card: "CardObjetivo" },
  escolher_cenario: { legivel: "Escolha do cenário" },
  solicitar_consentimento: { legivel: "Pedido de autorização", tag: "acao" },
  criar_plano: { legivel: "Criação do plano", tag: "acao", card: "CardPlano" },
  ativar_lembretes: { legivel: "Lembretes", tag: "acao", card: "ReciboAcao" },
  simular_contratacao: { legivel: "Simulação de contratação", tag: "acao", card: "ReciboAcao" },
  compartilhar_dados: { legivel: "Compartilhamento de dados", tag: "acao" },
  ajustar_plano: { legivel: "Ajuste do plano", tag: "acao", card: "ReciboAcao" },
  avancar_mes: { legivel: "Avanço de mês", tag: "diagnostico", card: "CardPlanejadoRealizado" },
  status_plano: { legivel: "Status do plano", tag: "diagnostico", card: "CardStatusPlano" },
};

export function nomeLegivel(nome: string): string {
  return CATALOGO[nome]?.legivel ?? "Consulta";
}

/** Nome legível em minúsculas para frases ("oportunidades de corte"). */
export function nomeEmFrase(nome: string): string {
  const legivel = nomeLegivel(nome);
  return legivel.charAt(0).toLowerCase() + legivel.slice(1);
}

const COPY_ERRO: Record<string, string> = {
  DADOS_INSUFICIENTES: "Tenho poucos meses de histórico para estimar sua sobra com segurança.",
  ENTRADA_INVALIDA: "Não entendi os valores desse pedido. Pode reformular?",
  PRAZO_IMPLAUSIVEL: "Esse prazo não é possível de simular. Tente outro prazo.",
  USUARIO_INEXISTENTE: "Não encontrei seus dados nesta demonstração.",
  SEM_PLANO_ATIVO: "Você ainda não tem um plano ativo. Crie o plano para acompanhar mês a mês.",
  FIM_DO_REPLAY: "A demonstração vai até dez/2025. Não há mais meses para avançar.",
};

/** Copy fixa pt-BR por código. `erro.mensagem` nunca é exibida. */
export function mensagemErro(codigo: string, nome: string): string {
  if (codigo === "INDISPONIVEL") return `Não consegui consultar ${nomeEmFrase(nome)} agora. Sigo com o que tenho.`;
  return COPY_ERRO[codigo] ?? "Algo deu errado nesta consulta. Sigo com o que tenho.";
}

export function podeTentarDeNovo(codigo: string): boolean {
  return codigo === "INDISPONIVEL";
}

export const MENSAGEM_FALHA_CONEXAO = "Não consegui falar com a Bússola agora.";

/** Frase enviada por "Tentar de novo" (contracts/eventos-agente.md §4). */
export function mensagemTentarDeNovo(nome: string): string {
  return `Tentar de novo: ${nomeLegivel(nome)}`;
}
