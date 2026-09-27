/** Confere a senha padrão de teste, compartilhada por todas as personas. */
export interface PasswordVerifier {
  /** Tempo constante: entrada ausente, longa ou que não é texto custa o mesmo e dá `false`. */
  verify(password: unknown): Promise<boolean>;
}
