import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BoasVindas } from "./BoasVindas";

describe("Boas-vindas · hierarquia e UX Writing", () => {
  it("mostra uma pergunta principal e mantém a intenção completa ao enviar", () => {
    const escolher = vi.fn();
    render(<BoasVindas nome="Fernando" onEscolher={escolher} desabilitado={false} />);

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "O que você quer realizar?" })).toBeTruthy();
    expect(screen.getAllByRole("button")).toHaveLength(4);

    fireEvent.click(screen.getByRole("button", { name: "Comprar um apartamento" }));
    expect(escolher).toHaveBeenCalledWith("Quero comprar meu primeiro apartamento");
  });

  it("mantém quatro escolhas acessíveis e evita ações quando indisponível", () => {
    const escolher = vi.fn();
    render(<BoasVindas onEscolher={escolher} desabilitado compacto />);
    const botao = screen.getByRole("button", { name: "Organizar dívidas" });
    expect(botao.hasAttribute("disabled")).toBe(true);
    fireEvent.click(botao);
    expect(escolher).not.toHaveBeenCalled();
  });
});
