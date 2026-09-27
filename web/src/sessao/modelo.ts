import type {
  Dados,
  EstadoJornada,
  EstadoSessao,
  Fonte,
  MotivoGuardrail,
  RespostaFerramenta,
  TagMensagem,
} from "../agente/tipos";
import type { NomeCard } from "./catalogo";

export type StatusFerramenta = "consultando" | "ok" | "erro";

export interface ItemBase {
  /** Chave estável para o React. */
  chave: string;
  ts: number;
}

export interface ItemMensagemCliente extends ItemBase {
  tipo: "mensagem_cliente";
  texto: string;
}

export interface ItemMensagemAgente extends ItemBase {
  tipo: "mensagem_agente";
  autor: string;
  texto: string;
  emStreaming: boolean;
  tag?: TagMensagem;
  respostasRapidas?: string[];
}

export interface ItemFerramenta extends ItemBase {
  tipo: "ferramenta";
  chamadaId: string;
  nome: string;
  /** Parâmetros já mascarados (sem PII). */
  args: Dados;
  status: StatusFerramenta;
  resposta?: RespostaFerramenta;
  inicio: number;
  fim?: number;
  /** Turno em que a chamada aconteceu (agrupamento do BlocoAnalise). */
  turno: number;
}

export interface ItemCard extends ItemBase {
  tipo: "card";
  turno: number;
  componente: NomeCard;
  chamadaId: string;
  nome: string;
  resposta: RespostaFerramenta;
  /** Outras respostas que o mesmo card combina (ex.: capacidade no diagnóstico). */
  complementos: Record<string, RespostaFerramenta>;
  /** Snapshot do estado no momento do card. */
  estado: EstadoSessao;
  recomendado?: string;
}

export interface ItemConsentimento extends ItemBase {
  tipo: "consentimento";
  acao: string;
  consentId: string;
  /** Dados do pedido (o que faz, o que não faz, dados usados). */
  pedido?: Dados;
}

export interface ItemGuardrail extends ItemBase {
  tipo: "guardrail";
  motivo: MotivoGuardrail;
  texto: string;
  respostasRapidas?: string[];
}

export interface ItemDivisorMes extends ItemBase {
  tipo: "divisor_mes";
  anomes: number;
}

export interface ItemFalhaConexao extends ItemBase {
  tipo: "falha_conexao";
  mensagem: string;
  /** Última mensagem do cliente, reenviada por "Tentar de novo". */
  reenviar?: string;
}

export type ItemConversa =
  | ItemMensagemCliente
  | ItemMensagemAgente
  | ItemFerramenta
  | ItemCard
  | ItemConsentimento
  | ItemGuardrail
  | ItemDivisorMes
  | ItemFalhaConexao;

export type TipoEventoAuditoria =
  | "sessao_iniciada"
  | "estado_alterado"
  | "ferramenta_chamada"
  | "consentimento_solicitado"
  | "consentimento_decidido"
  | "plano_criado"
  | "acao_executada"
  | "guardrail_bloqueio"
  | "acompanhamento_mes_avancado"
  | "desvio_detectado"
  | "rota_recalculada"
  | "plano_ajustado";

export interface EventoAuditoria {
  tipo_evento: TipoEventoAuditoria;
  ts: number;
  estado_jornada?: EstadoJornada;
  /** Texto curto a partir de nomes e códigos, nunca o texto do cliente. */
  resumo: string;
}

export interface RegistroFerramenta {
  chamadaId: string;
  nome: string;
  args: Dados;
  status: StatusFerramenta;
  inicio: number;
  fim?: number;
  fonte?: Fonte;
  avisos: string[];
  codigoErro?: string;
}

export interface PassoJornada {
  estado: EstadoJornada;
  ts: number;
}

export interface ModeloSessao {
  itens: ItemConversa[];
  estado: EstadoSessao;
  auditoria: EventoAuditoria[];
  jornada: PassoJornada[];
  ferramentas: RegistroFerramenta[];
  ocupado: boolean;
  turno: number;
  /** Contador para chaves estáveis dos itens. */
  seq: number;
  /** Rascunhos de texto parcial por autor (item em streaming). */
  rascunhos: Record<string, { chave: string; texto: string }>;
  erroConexao?: string;
}

export const MODELO_INICIAL: ModeloSessao = {
  itens: [],
  estado: {},
  auditoria: [],
  jornada: [],
  ferramentas: [],
  ocupado: false,
  turno: 0,
  seq: 0,
  rascunhos: {},
};
