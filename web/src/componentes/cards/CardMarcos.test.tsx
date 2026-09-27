import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Envelope, RespostaFerramenta } from "../../agente/tipos";
import { CATALOGO, mensagemErro } from "../../sessao/catalogo";
import type { ItemCard } from "../../sessao/modelo";
import { CardMarcos } from "./CardMarcos";

const sp = (s: string | null | undefined) => (s ?? "").replace(/\u00a0/g, " ");

// Envelope real de planejar_marcos (âncora, 300 mil em 24 meses, corte 202512).
const PROXIMO = {
  ordem: 1,
  nivel: 3,
  tipo: "ACUMULAR_PARTE_DA_META",
  titulo: "Acumular a primeira parte relevante da meta",
  indicador: "R$ 35.847,84 acumulados para o objetivo",
  valor_alvo: 35847.84,
  prazo_meses: 24,
  aporte_mensal: 1493.66,
  por_que: "É o que a sua capacidade sustentável constrói em 24 meses.",
  relacao_com_objetivo: "São 12% do objetivo já formados em patrimônio seu.",
};

const ENVELOPE: Envelope = {
  dados: {
    objetivo: { valor_alvo: 300000, prazo_meses: 24, prioridade: null },
    situacao: { renda_media: 7451.27, gasto_medio: 4614.52, sobra_mediana: 2489.44, recursos_disponiveis: 47597.68 },
    motivos: [
      {
        codigo: "PRAZO_NAO_CABE",
        observado: 10516.76,
        limite: 1493.66,
        explicacao: "Em 24 meses, o objetivo pede R$ 10.516,76 por mês.",
      },
    ],
    marcos: [
      PROXIMO,
      {
        ordem: 2,
        nivel: 4,
        tipo: "AJUSTAR_PRAZO",
        titulo: "Rever o prazo do objetivo, mantendo o valor",
        indicador: "R$ 300.000,00 alcançados em 169 meses",
        valor_alvo: 300000,
        prazo_meses: 169,
        aporte_mensal: 1493.66,
        por_que: "Com a capacidade atual, este é o prazo em que o objetivo fecha.",
        relacao_com_objetivo: "O valor continua o mesmo; muda o horizonte.",
      },
    ],
    proximo: PROXIMO,
    aporte_necessario: 10516.76,
    capacidade_sustentavel: 1493.66,
    trajetoria_incerta: false,
    ressalvas: ["Este marco melhora sua posição financeira, mas atingi-lo não garante o objetivo final."],
    regras: { meses_reserva: 3 },
  },
  fonte: {
    ferramenta: "planejar_marcos",
    tabelas: ["bussola_dados.perfil_mensal", "bussola_dados.parcelas"],
    periodo: { inicio: 202501, fim: 202512 },
  },
  avisos: ["Não há dado de patrimônio nem de investimentos nesta base."],
};

function card(envelope: Envelope): ItemCard {
  const resposta: RespostaFerramenta = { tipo: "envelope", envelope };
  return {
    tipo: "card",
    chave: "i1",
    ts: 0,
    turno: 1,
    componente: "CardMarcos",
    chamadaId: "c1",
    nome: "planejar_marcos",
    resposta,
    complementos: {},
    estado: {},
  };
}

function comDados(mudancas: Record<string, unknown>): Envelope {
  return { ...ENVELOPE, dados: { ...ENVELOPE.dados, ...mudancas } };
}

describe("CardMarcos", () => {
  it("envelope → objetivo, situação, próximo marco em destaque, trajetória e fonte", () => {
    render(<CardMarcos item={card(ENVELOPE)} />);
    const artigo = screen.getByRole("article", { name: "CardMarcos" });
    const texto = sp(artigo.textContent);

    expect(texto).toContain("R$ 300.000,00");
    expect(texto).toContain("24 meses");
    expect(texto).toContain("Em 24 meses, o objetivo pede R$ 10.516,76 por mês.");
    expect(texto).toContain("R$ 1.493,66");
    expect(texto).toContain("R$ 10.516,76");

    const proximo = within(artigo).getByLabelText("Próximo marco");
    expect(sp(proximo.textContent)).toContain("Acumular a primeira parte relevante da meta");
    expect(sp(proximo.textContent)).toContain("R$ 35.847,84");
    expect(sp(proximo.textContent)).toContain("São 12% do objetivo");

    // O marco seguinte aparece na trajetória, não no destaque.
    const seguintes = within(artigo).getByLabelText("Marcos seguintes");
    expect(sp(seguintes.textContent)).toContain("Rever o prazo do objetivo");
    expect(sp(seguintes.textContent)).toContain("169 meses");
    expect(sp(proximo.textContent)).not.toContain("Rever o prazo");

    // Chip de fonte e avisos do envelope.
    expect(within(artigo).getByRole("button", { name: /Marcos do objetivo · jan–dez\/2025/ })).toBeInTheDocument();
    expect(texto).toContain("Não há dado de patrimônio");
    expect(texto).toContain("não garante o objetivo final");
  });

  it("trajetória incerta → ressalva em âmbar e só o próximo marco", () => {
    render(
      <CardMarcos
        item={card(
          comDados({
            trajetoria_incerta: true,
            marcos: [PROXIMO],
            ressalvas: ["Hoje não há uma trajetória financeiramente responsável para esse objetivo."],
          }),
        )}
      />,
    );
    const artigo = screen.getByRole("article", { name: "CardMarcos" });
    expect(within(artigo).getByLabelText("Ressalvas")).toHaveClass("note-warn");
    expect(screen.queryByLabelText("Marcos seguintes")).toBeNull();
  });

  it("objetivo que cabe → sem motivos e sem marcos, e o card não inventa nada", () => {
    render(<CardMarcos item={card(comDados({ motivos: [], marcos: [], proximo: null }))} />);
    const artigo = screen.getByRole("article", { name: "CardMarcos" });
    expect(screen.queryByLabelText("Próximo marco")).toBeNull();
    expect(screen.queryByLabelText("Situação atual")).toBeNull();
    expect(sp(artigo.textContent)).toContain("R$ 300.000,00");
  });

  it("campo ausente vira — em vez de número calculado", () => {
    render(
      <CardMarcos
        item={card(
          comDados({
            proximo: { ordem: 1, nivel: 2, tipo: "FORMAR_RESERVA", titulo: "Formar a reserva", indicador: "" },
            marcos: [],
          }),
        )}
      />,
    );
    expect(sp(screen.getByLabelText("Próximo marco").textContent)).toContain("—");
  });

  it("catálogo liga planejar_marcos ao card e ao copy de erro", () => {
    expect(CATALOGO.planejar_marcos).toEqual({
      legivel: "Marcos do objetivo",
      tag: "recomendacao",
      card: "CardMarcos",
    });
    expect(mensagemErro("INDISPONIVEL", "planejar_marcos")).toContain("marcos do objetivo");
    expect(mensagemErro("DADOS_INSUFICIENTES", "planejar_marcos")).toContain("histórico");
  });
});
