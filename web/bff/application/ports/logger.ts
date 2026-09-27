/**
 * Campos de log permitidos (contratos §9). Nunca registrar senha, token,
 * cookie, login digitado ou texto de mensagem.
 */
export interface LogFields {
  evento?: string;
  session_id?: string;
  id_usuario?: string;
  latencia_ms?: number;
  erro_codigo?: string;
  /** Nome da classe da exceção, sem mensagem nem traceback. */
  excecao?: string;
}

export interface Logger {
  info(message: string, fields?: LogFields): void;
  warn(message: string, fields?: LogFields): void;
  error(message: string, fields?: LogFields): void;
}

export function exceptionName(error: unknown): string {
  return error instanceof Error ? error.name : typeof error;
}
