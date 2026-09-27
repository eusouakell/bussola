// Port do login por persona (R5): a apresentação e o hook dependem desta
// interface, nunca da classe concreta `ClienteAuth`. Assim um duplo de teste é
// um objeto literal, e não uma instância de infraestrutura com `vi.spyOn`.

export interface Persona {
  login: string;
  displayName: string;
  summary: string;
}

/** Falha com a mensagem em pt-BR do envelope `{erro: {codigo, mensagem}}`. */
export class FalhaAuth extends Error {
  readonly codigo: string;

  constructor(codigo: string, mensagem: string) {
    super(mensagem);
    this.name = "FalhaAuth";
    this.codigo = codigo;
  }
}

export interface PortalAuth {
  listarPersonas(): Promise<Persona[]>;
  /** Persona logada ou `null` sem sessão. */
  sessaoAtual(): Promise<Persona | null>;
  entrar(login: string, senha: string): Promise<Persona>;
  sair(): Promise<void>;
}
