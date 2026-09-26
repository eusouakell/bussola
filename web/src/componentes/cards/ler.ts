// Leitura defensiva dos `dados` dos envelopes: o card mostra "—" quando um
// campo falta, nunca calcula um substituto.
import type { Dados } from "../../agente/tipos";

export function num(d: Dados | undefined, chave: string): number | undefined {
  const v = d?.[chave];
  return typeof v === "number" && !Number.isNaN(v) ? v : undefined;
}

export function txt(d: Dados | undefined, chave: string): string | undefined {
  const v = d?.[chave];
  return typeof v === "string" && v !== "" ? v : undefined;
}

export function bool(d: Dados | undefined, chave: string): boolean | undefined {
  const v = d?.[chave];
  return typeof v === "boolean" ? v : undefined;
}

export function obj(d: Dados | undefined, chave: string): Dados | undefined {
  const v = d?.[chave];
  return typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Dados) : undefined;
}

export function lista(d: Dados | undefined, chave: string): Dados[] {
  const v = d?.[chave];
  return Array.isArray(v) ? v.filter((x): x is Dados => typeof x === "object" && x !== null && !Array.isArray(x)) : [];
}

export function textos(d: Dados | undefined, chave: string): string[] {
  const v = d?.[chave];
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

/** "acelerado" → "Acelerado". */
export function capitalizar(texto: string | undefined): string {
  if (!texto) return "—";
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}
