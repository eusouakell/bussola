// Tradução das falhas para HTTP. O cliente recebe o envelope
// `{erro: {codigo, mensagem}}` em pt-BR; detalhes ficam só no log, pelos
// campos permitidos.
import { AgentUnavailable, InvalidCredentials, NotAuthenticated, NotFound, TooManyAttempts } from "../../application/errors.ts";
import { exceptionName, type Logger } from "../../application/ports/logger.ts";
import { InvalidChatMessage } from "../../domain/chatMessage.ts";

export class HttpError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
  }
}

export const invalidRequest = () => new HttpError(400, "PEDIDO_INVALIDO", "Pedido inválido.");
export const notFound = () => new HttpError(404, "NAO_ENCONTRADO", "Não encontrado.");

export function toHttpError(error: unknown, logger: Logger): HttpError {
  if (error instanceof HttpError) return error;
  if (error instanceof InvalidChatMessage) return invalidRequest();
  if (error instanceof InvalidCredentials) return new HttpError(401, "CREDENCIAIS_INVALIDAS", "Login ou senha inválidos.");
  if (error instanceof TooManyAttempts) {
    return new HttpError(429, "MUITAS_TENTATIVAS", "Muitas tentativas. Tente de novo em alguns minutos.");
  }
  if (error instanceof NotAuthenticated) return new HttpError(401, "NAO_AUTENTICADO", "Entre com uma persona para continuar.");
  if (error instanceof NotFound) return notFound();
  if (error instanceof AgentUnavailable) {
    logger.warn("agente indisponível", { evento: "agente_indisponivel", erro_codigo: error.code });
    return new HttpError(502, "AGENTE_INDISPONIVEL", "O assistente não respondeu. Tente de novo.");
  }
  logger.error("erro interno", { evento: "erro_interno", excecao: exceptionName(error) });
  return new HttpError(503, "INDISPONIVEL", "Serviço indisponível no momento.");
}
