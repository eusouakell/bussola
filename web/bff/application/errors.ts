// Falhas dos casos de uso. A camada de apresentação traduz cada uma para
// status HTTP e mensagem ao cliente; aqui as mensagens são só para depuração.
export class ApplicationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

export class InvalidCredentials extends ApplicationError {
  constructor() {
    super("login ou senha inválidos");
  }
}

export class TooManyAttempts extends ApplicationError {
  constructor() {
    super("muitas tentativas de login");
  }
}

export class NotAuthenticated extends ApplicationError {
  constructor() {
    super("sem sessão de login válida");
  }
}

export class NotFound extends ApplicationError {
  constructor() {
    super("recurso inexistente ou de outro login");
  }
}

export class AgentUnavailable extends ApplicationError {
  /** Código curto para log (`HTTP_500`, `SEM_RESPOSTA`...), sem dados do pedido. */
  readonly code: string;

  constructor(code: string) {
    super(`agente indisponível: ${code}`);
    this.code = code;
  }
}
