import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Consentimento } from "../../agente/tipos";
import type { ItemConsentimento } from "../../sessao/modelo";
import { CardConsentimento } from "./CardConsentimento";

const item: ItemConsentimento = {
  tipo: "consentimento",
  chave: "i9",
  ts: 0,
  acao: "criar_plano",
  consentId: "c-0001-7f3a",
  pedido: {
    resumo: "Criar o plano Primeiro apartamento",
    o_que_faz: "Registrar o plano e acompanhar seu progresso mês a mês.",
    o_que_nao_faz: "Mover dinheiro, contratar produtos ou compartilhar seus dados.",
    dados_usados: "Seu extrato de jan–jun/2025.",
  },
};

describe("CardConsentimento", () => {
  it("pendente → pedido com as 3 colunas; Autorizar envia 'sim' e Agora não envia 'não'", () => {
    const onEnviar = vi.fn();
    const pendente: Consentimento = { consent_id: item.consentId, status: "pendente" };
    render(<CardConsentimento item={item} consentimento={pendente} onEnviar={onEnviar} ocupado={false} />);
    const artigo = screen.getByRole("article", { name: "CardConsentimento" });
    expect(artigo.textContent).toContain("O que vou fazer");
    expect(artigo.textContent).toContain("O que não vou fazer");
    expect(artigo.textContent).toContain("Dados usados");
    expect(artigo.textContent).toContain("Mover dinheiro, contratar produtos");
    fireEvent.click(screen.getByRole("button", { name: "Autorizar" }));
    fireEvent.click(screen.getByRole("button", { name: "Agora não" }));
    expect(onEnviar.mock.calls).toEqual([["sim"], ["não"]]);
  });

  it("aceito → recibo com data, hora e ID mascarado", () => {
    const aceito: Consentimento = { consent_id: item.consentId, status: "aceito", ts: "2026-09-26T17:32:00Z" };
    render(<CardConsentimento item={item} consentimento={aceito} onEnviar={vi.fn()} ocupado={false} />);
    const recibo = screen.getByRole("status", { name: "Recibo de consentimento" });
    expect(recibo.textContent).toContain("Autorizado");
    expect(recibo.textContent).toContain("26/09/2026 14:32");
    expect(recibo.textContent).toContain("consentimento c-00…7f3a");
    expect(screen.queryByRole("button", { name: "Autorizar" })).toBeNull();
  });

  it("recusado → recibo neutro; outro consent_id na mesma ação → pedido encerrado", () => {
    const { rerender } = render(
      <CardConsentimento item={item} consentimento={{ consent_id: item.consentId, status: "recusado", ts: 1790000000 }} onEnviar={vi.fn()} ocupado={false} />,
    );
    expect(screen.getByRole("status").textContent).toContain("Não autorizado");
    rerender(<CardConsentimento item={item} consentimento={{ consent_id: "c-0002", status: "pendente" }} onEnviar={vi.fn()} ocupado={false} />);
    expect(screen.getByRole("status").textContent).toContain("Pedido encerrado");
  });
});
