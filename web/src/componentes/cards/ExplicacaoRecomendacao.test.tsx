import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ItemCard } from "../../sessao/modelo";
import { avisosContextuais, ExplicacaoRecomendacao } from "./ExplicacaoRecomendacao";

function card(dados: Record<string, unknown>, avisos: string[] = []): ItemCard {
  return {
    tipo: "card",
    chave: "fonte-001",
    ts: 0,
    turno: 1,
    componente: "ExplicacaoRecomendacao",
    chamadaId: "consulta-001",
    nome: "buscar_contexto_financeiro",
    estado: {},
    complementos: {},
    resposta: {
      tipo: "envelope",
      envelope: {
        dados,
        fonte: { tabelas: [], periodo: { inicio: 202501, fim: 202506 } },
        avisos,
      },
    },
  } as unknown as ItemCard;
}

describe("Fontes da orientação · apresentação opcional", () => {
  it("não cria cartão redundante quando não há fonte nem alerta relevante", () => {
    const { container } = render(
      <ExplicacaoRecomendacao item={card({}, ["Resposta simulada pelo front; regravar após o ciclo 003", "Conteúdo educativo e geral, não é recomendação individual. Confira a norma em vigor no site do Banco Central."])} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("oferece fontes verificáveis sob demanda, sem bloco de recomendação", () => {
    render(
      <ExplicacaoRecomendacao
        item={card({ trechos: [{ trecho_id: "a", titulo: "Orientação pública", texto: "Texto da fonte consultada", fonte: { nome: "Banco Central", referencia: "2026" } }] })}
      />,
    );
    expect(screen.getByText("Fontes consultadas")).toBeInTheDocument();
    expect(screen.queryByText("Base de conhecimento")).not.toBeInTheDocument();
    expect(screen.queryByText(/Esta orientação considera a simulação financeira/)).not.toBeInTheDocument();
    const detalhes = screen.getByText("Fontes consultadas").closest("details");
    expect(detalhes).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Fontes consultadas"));
    expect(detalhes).toHaveAttribute("open");
    expect(screen.getByText("Texto da fonte consultada")).toBeInTheDocument();
  });

  it("mantém avisos materiais visíveis e filtra somente ruído conhecido", () => {
    expect(avisosContextuais(["Dados insuficientes", "Resposta simulada pelo front; regravar após o ciclo 003"])).toEqual(["Dados insuficientes"]);
    render(<ExplicacaoRecomendacao item={card({}, ["Não foi possível conferir a fonte atual."])} />);
    expect(screen.getByRole("status")).toHaveTextContent("Não foi possível conferir a fonte atual.");
  });
});
