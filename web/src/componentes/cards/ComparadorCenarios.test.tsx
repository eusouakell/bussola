import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ItemCard } from "../../sessao/modelo";
import { CardCenario, ComparadorCenarios, explicarConsequencia } from "./ComparadorCenarios";

const acelerado = {
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
};

const conservador = {
  nome: "conservador",
  pct_capacidade: 0.4,
  prazo_meses: 44,
  aporte_mensal: 691.6,
  viavel: true,
  cortes_sugeridos: [],
  trade_offs: ["Demora mais que o prazo escolhido."],
};

const equilibrado = {
  nome: "equilibrado",
  pct_capacidade: 0.6,
  prazo_meses: 29,
  aporte_mensal: 1037.4,
  viavel: true,
  cortes_sugeridos: [],
  trade_offs: ["Compromete 60% da sobra mensal mediana (R$ 1.037/mês)."],
};

function comparar(): ItemCard {
  return {
    tipo: "card",
    chave: "c1",
    ts: 0,
    turno: 1,
    componente: "ComparadorCenarios",
    chamadaId: "f1",
    nome: "comparar_cenarios",
    resposta: {
      tipo: "envelope",
      envelope: {
        dados: { cenarios: [conservador, equilibrado, acelerado] },
        fonte: { ferramenta: "comparar_cenarios", tabelas: [] },
        avisos: [],
      },
    },
    complementos: {},
    estado: { objetivo: { prazo_meses: 24 } },
  };
}

describe("Comparação de planos · linguagem simples e carga cognitiva", () => {
  it("mostra cortes essenciais antes dos detalhes e mantém os números auditáveis", () => {
    const escolher = vi.fn();
    render(<CardCenario cenario={acelerado} recomendado escolhido={false} bloqueado={false} prazoObjetivo={24} onEscolher={escolher} />);

    const card = screen.getByRole("article", { name: "Cenário Acelerado, em destaque" });
    expect(card.textContent).toContain("Plano de 19 meses");
    expect(card.textContent).toContain("Guardar por mês");
    expect(card.textContent).toContain("277,65");
    expect(card.textContent).toContain("1.383,20");
    expect(card.textContent).toContain("96%");
    expect(card.textContent).not.toContain("sobra mensal mediana");

    const detalhes = screen.getByText("Entenda os valores deste plano").closest("details");
    expect(detalhes).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Entenda os valores deste plano"));
    expect(detalhes).toHaveAttribute("open");
    fireEvent.click(screen.getByRole("button", { name: "Escolher plano de 19 meses" }));
    expect(escolher).toHaveBeenCalledWith("acelerado");
  });

  it("diz quantos meses ultrapassam o prazo, sem chamar a opção de inviável", () => {
    render(<CardCenario cenario={conservador} recomendado={false} escolhido={false} bloqueado={false}
      prazoObjetivo={24} onEscolher={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Plano de 44 meses", level: 3 })).toBeInTheDocument();
    expect(screen.getByText("20 meses depois do prazo que você escolheu.")).toBeInTheDocument();
    expect(screen.queryByText(/viabilidade financeira/i)).toBeNull();
  });

  it("mostra uma alternativa por vez e mantém três opções de escolha", () => {
    const enviar = vi.fn();
    render(<ComparadorCenarios item={comparar()} onEnviar={enviar} ocupado={false} />);
    expect(screen.getAllByRole("article", { name: /Cenário/ })).toHaveLength(1);
    const opcoes = screen.getByRole("group", { name: "Escolha um prazo para comparar" });
    expect(opcoes.querySelectorAll("button")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: /29 meses/i }));
    expect(screen.getByRole("heading", { name: "Plano de 29 meses" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Plano de 19 meses" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Escolher plano de 29 meses" }));
    expect(enviar).toHaveBeenCalledWith("Quero o caminho equilibrado");
  });

  it("troca jargão conhecido sem mudar a consequência financeira", () => {
    const texto = explicarConsequencia("Compromete 60% da sobra mensal mediana (R$ 1.037/mês).");
    expect(texto).toContain("60% do dinheiro que costuma sobrar");
    expect(texto).not.toContain("mediana");
  });
});
