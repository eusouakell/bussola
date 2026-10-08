import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CardCenario } from "./ComparadorCenarios";

describe("CardCenario · explicabilidade financeira", () => {
  it("separa aporte-base, cortes adicionais e total antes de oferecer escolha", () => {
    const escolher = vi.fn();
    render(
      <CardCenario
        cenario={{
          nome: "acelerado",
          pct_capacidade: 0.8,
          prazo_meses: 19,
          aporte_mensal: 1660.85,
          viavel: true,
          cortes_sugeridos: [
            { micro: "Restaurantes", valor_mensal: 96.61 },
            { micro: "Compras", valor_mensal: 85.5 },
            { micro: "Assinaturas", valor_mensal: 54.01 },
            { micro: "Eletrônicos", valor_mensal: 13.39 },
            { micro: "Outros entretenimentos", valor_mensal: 11.14 },
            { micro: "Outras comidas e bebidas", valor_mensal: 7.43 },
            { micro: "Cinema", valor_mensal: 6.41 },
            { micro: "Videogames", valor_mensal: 1.86 },
            { micro: "Viagens", valor_mensal: 1.3 },
          ],
          trade_offs: [
            "Compromete 80% da sobra mensal mediana (R$ 1.383/mês).",
            "Exige reduzir gastos com restaurantes.",
          ],
        }}
        recomendado
        escolhido={false}
        bloqueado={false}
        prazoObjetivo={24}
        onEscolher={escolher}
      />,
    );

    const artigo = screen.getByRole("article", { name: "Cenário Acelerado, em destaque" });
    expect(artigo.textContent).toContain("Em destaque · exige cortes");
    expect(artigo.textContent).toContain("1.383,20");
    expect(artigo.textContent).toContain("277,65");
    expect(artigo.textContent).toContain("96%");
    expect(artigo.textContent).not.toContain("Compromete 80% da sobra mensal");

    fireEvent.click(screen.getByRole("button", { name: "Escolher plano de 19 meses" }));
    expect(escolher).toHaveBeenCalledWith("acelerado");
  });

  it("não inventa economias adicionais quando não há cortes", () => {
    render(
      <CardCenario
        cenario={{
          nome: "conservador",
          pct_capacidade: 0.4,
          prazo_meses: 44,
          aporte_mensal: 691.6,
          cortes_sugeridos: [],
          trade_offs: [],
        }}
        recomendado={false}
        escolhido={false}
        bloqueado={false}
        prazoObjetivo={24}
        onEscolher={vi.fn()}
      />,
    );
    expect(screen.queryByText("Como se forma o aporte")).toBeNull();
    expect(screen.getByRole("button", { name: "Escolher plano de 44 meses" })).toBeTruthy();
  });
});
