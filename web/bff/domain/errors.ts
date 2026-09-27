// Erro de regra de negócio. A mensagem nunca repete dado do usuário.
export class DomainError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}
