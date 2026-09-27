import { toPublicPersona, type PublicPersona } from "../../domain/userAccount.ts";
import type { UserRepository } from "../ports/userRepository.ts";

/** Personas em destaque para a tela de login, sem `id_usuario`. */
export class ListPersonas {
  private readonly users: UserRepository;

  constructor(users: UserRepository) {
    this.users = users;
  }

  async execute(): Promise<PublicPersona[]> {
    return (await this.users.listFeatured()).map(toPublicPersona);
  }
}
