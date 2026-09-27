// Tipos do contrato front ↔ agente (specs/008-front-web/contracts/eventos-agente.md).
// Subconjunto do `Event` do ADK em camelCase e envelopes do MCP (contratos §5).

export type EstadoJornada = "OBJETIVO" | "ENTENDER" | "ANTECIPAR" | "ORIENTAR" | "AGIR" | "ACOMPANHAR";

export const ESTADOS_JORNADA: readonly EstadoJornada[] = [
  "OBJETIVO",
  "ENTENDER",
  "ANTECIPAR",
  "ORIENTAR",
  "AGIR",
  "ACOMPANHAR",
];

export interface Periodo {
  inicio: number;
  fim: number;
}

export interface Fonte {
  ferramenta: string;
  tabelas: string[];
  periodo?: Periodo | null;
}

export interface Envelope<D = Record<string, unknown>> {
  dados: D;
  fonte: Fonte;
  avisos: string[];
}

export interface ErroEnvelope {
  erro: { codigo: string; mensagem: string };
}

export type Dados = Record<string, unknown>;

export type RespostaFerramenta =
  | { tipo: "envelope"; envelope: Envelope }
  | { tipo: "erro"; codigo: string }
  | { tipo: "cru"; dados: Dados };

export interface ChamadaFuncao {
  id?: string;
  name: string;
  args?: Dados;
}

export interface RespostaFuncao {
  id?: string;
  name: string;
  response: unknown;
}

export interface Parte {
  text?: string;
  /** Raciocínio do modelo (nunca exibido). */
  thought?: boolean;
  functionCall?: ChamadaFuncao;
  functionResponse?: RespostaFuncao;
}

export type MotivoGuardrail =
  | "outro_cliente"
  | "ignorar_instrucoes"
  | "infra"
  | "promessa_credito"
  | "compartilhar_dados"
  | "atividade_ilicita"
  | "fora_do_escopo";

export type TagMensagem = "diagnostico" | "simulacao" | "recomendacao" | "acao";

export interface MetadadosBussola {
  respostas_rapidas?: string[];
  tag?: TagMensagem;
  guardrail?: MotivoGuardrail;
  recomendado?: string;
}

export interface EventoAdk {
  id?: string;
  invocationId?: string;
  author: string;
  timestamp?: number;
  partial?: boolean;
  content?: { role?: string; parts?: Parte[] };
  actions?: { stateDelta?: Dados };
  customMetadata?: { bussola?: MetadadosBussola } & Dados;
  /** Erro de turno (`data: {"error": …}` no SSE). */
  error?: string;
}

export type StatusConsentimento = "pendente" | "aceito" | "recusado";

export interface Consentimento {
  consent_id: string;
  status: StatusConsentimento;
  ts?: string | number;
  resumo?: string;
}

export interface Objetivo {
  tipo?: string;
  descricao?: string;
  valor_alvo?: number | null;
  prazo_meses?: number | null;
  prioridade?: string;
}

export interface EstadoSessao {
  id_usuario?: string;
  ate_anomes?: number;
  estado_jornada?: EstadoJornada;
  objetivo?: Objetivo | null;
  cenarios?: Dados | null;
  cenario_escolhido?: string | null;
  ultimas_fontes?: Fonte[];
  consentimentos?: Record<string, Consentimento>;
  plano_id?: string | null;
  acompanhamento?: Dados[];
  [chave: string]: unknown;
}
