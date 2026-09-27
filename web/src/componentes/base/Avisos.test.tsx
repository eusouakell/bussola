import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Avisos } from "./Avisos";

/** Avisos de negócio: continuam como alerta âmbar (FR-009). */
const NEGOCIO = ["Saldo ficou negativo em 2 meses do período.", "Gasto superou a renda em 1 mês do período."];
/** Strings das capturas da demo: jargão interno, nunca vai para a tela (BUG-06). */
const JARGAO = [
  "Resposta de exemplo do mock (corte 202506).",
  "Resposta de exemplo do mock, calculada para valor_alvo=30000 e prazo_meses=24.",
];
/** Redação de cliente esperada do backend para os mesmos avisos (BUG-06). */
const DEMONSTRACAO = [
  "Números de exemplo desta demonstração.",
  "Simulação de exemplo desta demonstração, com valores e prazo arredondados.",
  "Exemplo desta demonstração: números com dados até junho de 2025.",
  "Exemplo desta demonstração: simulação para uma meta de R$ 30.000,00 em 24 meses.",
];
const SIMULADA = "Resposta simulada pelo front; regravar após o ciclo 004";

function alertas(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>(".note-warn")];
}

function badges(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>(".badge")];
}

describe("Avisos", () => {
  it("sem avisos não renderiza nada", () => {
    const { container, rerender } = render(<Avisos avisos={undefined} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<Avisos avisos={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("aviso repetido aparece uma vez só, sem chave React duplicada (BUG-05b)", () => {
    const erro = vi.spyOn(console, "error").mockImplementation(() => {});
    const repetido = "Tenho poucos meses de histórico para estimar sua sobra com segurança.";
    render(<Avisos avisos={[repetido, repetido, NEGOCIO[0], repetido]} />);
    expect(alertas().map((n) => n.textContent)).toEqual([repetido, NEGOCIO[0]]);
    expect(screen.getAllByText(repetido)).toHaveLength(1);
    expect(erro).not.toHaveBeenCalled();
    erro.mockRestore();
  });

  it("aviso de negócio continua como alerta âmbar, não como badge", () => {
    render(<Avisos avisos={NEGOCIO} />);
    expect(alertas()).toHaveLength(2);
    expect(badges()).toHaveLength(0);
    for (const aviso of NEGOCIO) expect(screen.getByText(aviso)).toBeInTheDocument();
  });

  it.each(DEMONSTRACAO)("aviso de demonstração vira badge compacto: %s", (aviso) => {
    render(<Avisos avisos={[aviso]} />);
    expect(alertas()).toHaveLength(0);
    const [badge] = badges();
    expect(badge).toHaveClass("badge-warn");
    // legível na tela e anunciável (texto + title)
    expect(badge).toHaveTextContent(aviso);
    expect(badge).toHaveAttribute("title", aviso);
  });

  it("aviso simulado do front continua badge com o ciclo", () => {
    render(<Avisos avisos={[SIMULADA]} />);
    expect(alertas()).toHaveLength(0);
    expect(badges()[0]).toHaveTextContent("Resposta simulada pelo front · ciclo 004");
  });

  it.each(JARGAO)("jargão interno não chega à tela: %s", (aviso) => {
    const { container } = render(<Avisos avisos={[aviso]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("jargão some e o aviso de negócio do mesmo envelope permanece", () => {
    render(<Avisos avisos={[...JARGAO, NEGOCIO[0], ...DEMONSTRACAO]} />);
    const texto = document.body.textContent ?? "";
    for (const proibido of ["mock", "valor_alvo", "prazo_meses", "202506"]) expect(texto).not.toContain(proibido);
    expect(alertas().map((n) => n.textContent)).toEqual([NEGOCIO[0]]);
    expect(badges()).toHaveLength(DEMONSTRACAO.length);
  });

  it("demonstração repetida também deduplica", () => {
    render(<Avisos avisos={[DEMONSTRACAO[0], DEMONSTRACAO[0], SIMULADA, SIMULADA]} />);
    expect(badges()).toHaveLength(2);
  });
});
