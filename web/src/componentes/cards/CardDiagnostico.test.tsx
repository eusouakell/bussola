import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import goldensJson from "../../../fixtures/goldens.json";
import type { Envelope, RespostaFerramenta } from "../../agente/tipos";
import type { ItemCard } from "../../sessao/modelo";
import { CardDiagnostico } from "./CardDiagnostico";

const GOLDENS = goldensJson as unknown as { ferramentas: Record<string, Envelope> };
const sp = (s: string | null | undefined) => (s ?? "").replace(/\u00a0/g, " ");

function envelope(chave: string): RespostaFerramenta {
  return { tipo: "envelope", envelope: GOLDENS.ferramentas[chave] };
}

function card(principal: RespostaFerramenta, complementos: Record<string, RespostaFerramenta> = {}): ItemCard {
  return {
    tipo: "card",
    chave: "i1",
    ts: 0,
    turno: 1,
    componente: "CardDiagnostico",
    chamadaId: "c1",
    nome: "perfil_financeiro",
    resposta: principal,
    complementos,
    estado: {},
  };
}

describe("CardDiagnostico", () => {
  it("golden perfil + capacidade até 202506 → valores formatados, fontes e avisos", () => {
    render(
      <CardDiagnostico
        item={card(envelope("perfil_financeiro__ate_202506"), {
          capacidade_poupanca: envelope("capacidade_poupanca__ate_202506"),
        })}
      />,
    );
    const artigo = screen.getByRole("article", { name: "CardDiagnostico" });
    const texto = sp(artigo.textContent);
    expect(texto).toContain("R$ 6.691,39");
    expect(texto).toContain("R$ 4.789,93");
    expect(texto).toContain("R$ 1.729,00");
    expect(texto).toContain("média R$ 1.901,47");
    expect(texto).toContain("-R$ 2.072,31");
    expect(texto).toContain("R$ 19.023,89");
    // uma fonte por ferramenta
    expect(within(artigo).getByRole("button", { name: /Perfil financeiro · jan–jun\/2025/ })).toBeInTheDocument();
    expect(within(artigo).getByRole("button", { name: /Capacidade de poupança · jan–jun\/2025/ })).toBeInTheDocument();
    // avisos âmbar das duas ferramentas
    expect(texto).toContain("Saldo ficou negativo em 2 meses do período.");
    expect(texto).toContain("Gasto superou a renda em 1 mês do período.");
  });

  it("DADOS_INSUFICIENTES da capacidade vira aviso âmbar dentro do card (E4)", () => {
    render(
      <CardDiagnostico
        item={card(envelope("perfil_financeiro__ate_202506"), {
          capacidade_poupanca: { tipo: "erro", codigo: "DADOS_INSUFICIENTES" },
        })}
      />,
    );
    const nota = screen.getByRole("note");
    expect(nota).toHaveClass("note-warn");
    expect(nota.textContent).toContain("Tenho poucos meses de histórico");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("perfil e capacidade com o mesmo código mostram a frase uma vez só (BUG-05b)", () => {
    const copy = "Tenho poucos meses de histórico para estimar sua sobra com segurança.";
    render(
      <CardDiagnostico
        item={card(
          { tipo: "erro", codigo: "DADOS_INSUFICIENTES" },
          { capacidade_poupanca: { tipo: "erro", codigo: "DADOS_INSUFICIENTES" } },
        )}
      />,
    );
    expect(screen.getAllByRole("note")).toHaveLength(1);
    expect(screen.getAllByText(copy)).toHaveLength(1);
  });

  it("aviso repetido nas duas ferramentas aparece uma vez só (BUG-05b)", () => {
    const aviso = "Saldo ficou negativo em 2 meses do período.";
    render(
      <CardDiagnostico
        item={card(envelope("perfil_financeiro__ate_202506"), {
          capacidade_poupanca: envelope("perfil_financeiro__ate_202506"),
        })}
      />,
    );
    expect(screen.getAllByText(aviso)).toHaveLength(1);
  });
});
