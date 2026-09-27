import type { EstadoSessao, EventoAdk } from "./tipos";

export type Modo = "simulado" | "ao-vivo";

export interface InicioSessao {
  sessionId: string;
  estado: EstadoSessao;
  /** Eventos do início (o simulado emite o `stateDelta` inicial). */
  eventos: EventoAdk[];
}

/**
 * Cenários de borda que o apresentador liga na barra de demonstração. Faz
 * parte do port porque quem liga é a UI e quem implementa é o transporte; o
 * transporte ao vivo simplesmente não oferece `configurarBordas`.
 */
export interface Bordas {
  /** E3: `oportunidades_corte` indisponível na próxima consulta. */
  e3: boolean;
  /** E4: `capacidade_poupanca` com dados insuficientes. */
  e4: boolean;
  /** E5: respostas lentas (skeleton e cursor de digitação). */
  e5: boolean;
}

export const SEM_BORDAS: Bordas = { e3: false, e4: false, e5: false };

/** Interface comum aos transportes ao vivo (ADK) e simulado (R5). */
export interface Transporte {
  readonly modo: Modo;
  iniciar(): Promise<InicioSessao>;
  enviar(texto: string, sinal?: AbortSignal): AsyncIterable<EventoAdk>;
  /** Estado autoritativo depois do turno (ao vivo: GET da sessão). */
  ressincronizar?(): Promise<EstadoSessao | null>;
  /** Liga ou desliga cenários de borda; ausente no transporte ao vivo (R5). */
  configurarBordas?(bordas: Partial<Bordas>): void;
}

/** Fábrica injetada em `useSessao`: o hook não conhece implementação concreta. */
export type FabricaTransporte = (modo: Modo, bordas?: Bordas) => Transporte;

export class FalhaConexao extends Error {
  constructor(motivo: string) {
    super(motivo);
    this.name = "FalhaConexao";
  }
}
