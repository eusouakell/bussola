// Apoio aos testes do BFF: contas sintéticas e relógio manual.
import { randomUUID } from "node:crypto";
import type { UserAccount } from "../domain/userAccount.ts";

export function account(login: string, overrides: Partial<UserAccount> = {}): UserAccount {
  return {
    login,
    idUsuario: randomUUID(),
    displayName: `Persona ${login}`,
    summary: "Massa de dados sintética.",
    featured: true,
    ...overrides,
  };
}

export function userRow(login: string, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    login,
    id_usuario: randomUUID(),
    display_name: `Persona ${login}`,
    summary: "Massa de dados sintética.",
    featured: true,
    ...overrides,
  };
}

export class ManualClock {
  value: number;

  constructor(start = 1_000_000) {
    this.value = start;
  }

  now = (): number => this.value;

  advance(ms: number): void {
    this.value += ms;
  }
}
