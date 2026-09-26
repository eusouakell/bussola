import type { EstadoSessao, EventoAdk } from "./tipos";

export type Modo = "simulado" | "ao-vivo";

export interface InicioSessao {
  sessionId: string;
  estado: EstadoSessao;
  /** Eventos do início (o simulado emite o `stateDelta` inicial). */
  eventos: EventoAdk[];
}

/** Interface comum aos transportes ao vivo (ADK) e simulado (R5). */
export interface Transporte {
  readonly modo: Modo;
  iniciar(): Promise<InicioSessao>;
  enviar(texto: string, sinal?: AbortSignal): AsyncIterable<EventoAdk>;
  /** Estado autoritativo depois do turno (ao vivo: GET da sessão). */
  ressincronizar?(): Promise<EstadoSessao | null>;
}

export class FalhaConexao extends Error {
  constructor(motivo: string) {
    super(motivo);
    this.name = "FalhaConexao";
  }
}
