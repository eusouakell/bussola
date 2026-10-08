import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// Gate mínimo: cobre o texto comum dos CTAs. Não substitui auditoria WCAG no navegador.
const css = readFileSync("src/app.css", "utf8");

function corToken(nome: string): string {
  const resultado = css.match(new RegExp(`--${nome}:\\s*(#[0-9a-fA-F]{6})\\s*;`));
  if (!resultado) throw new Error(`Token ausente: ${nome}`);
  return resultado[1].toLowerCase();
}

function luminancia(hex: string): number {
  const rgb = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const canais = rgb.map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2];
}

function contraste(a: string, b: string): number {
  const [clara, escura] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (clara + 0.05) / (escura + 0.05);
}

describe("Gate de contraste dos tokens", () => {
  it("garante 4,5:1 para texto branco de CTA primário", () => {
    expect(css).toMatch(/\.btn-primary\s*\{[^}]*color:\s*#fff\s*;/s);
    expect(contraste("#ffffff", corToken("accent-cta"))).toBeGreaterThanOrEqual(4.5);
  });

  it("evita divergência entre os tokens do Tailwind e os tokens da aplicação", () => {
    expect(corToken("color-accent-cta")).toBe(corToken("accent-cta"));
    expect(corToken("color-accent-ink")).toBe(corToken("accent-ink"));
  });
});
