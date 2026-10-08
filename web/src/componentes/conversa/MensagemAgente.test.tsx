import { render, screen } from "@testing-library/react";
import { MensagemAgente } from "./MensagemAgente";

function renderizar(texto: string, emStreaming = false) {
  return render(<MensagemAgente item={{ tipo: "mensagem_agente", chave: "m1", ts: 0, autor: "bussola", texto, emStreaming }} />);
}

describe("MensagemAgente", () => {
  it("renderiza o markdown do modelo sem mostrar a marcação", () => {
    const { container } = renderizar(
      [
        "Analisei **janeiro a junho**:",
        "",
        "### 1. Sua situação",
        "* **Renda média:** R$ 6.691,39 (*perfil_financeiro*).",
        "* Sobra mediana de R$ 1.729,00.",
        "",
        "---",
        "",
        "1. Entrada",
        "2. Parcela",
      ].join("\n"),
    );
    expect(container.textContent).not.toMatch(/###|\*\*|---|^\*/m);
    expect(screen.getByRole("heading", { name: "1. Sua situação", level: 4 })).toBeInTheDocument();
    expect(screen.getByText("perfil_financeiro").tagName).toBe("EM");
    expect(container.querySelectorAll("ul > li")).toHaveLength(2);
    expect(container.querySelectorAll("ol > li")).toHaveLength(2);
  });

  it("mantém níveis de títulos legíveis por leitores de tela", () => {
    const { container } = renderizar("# Visão geral\n\n## Seus números\n\n### Próximos passos");
    expect(screen.getByRole("heading", { name: "Visão geral", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Seus números", level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Próximos passos", level: 4 })).toBeInTheDocument();
    expect(container.querySelector("p > strong")).toBeNull();
  });

  it("lista numerada separada por linha em branco continua a contagem", () => {
    const { container } = renderizar("1. Entrada\n\n2. Parcela");
    const listas = container.querySelectorAll("ol");
    expect(listas).toHaveLength(2);
    expect(listas[1].getAttribute("start")).toBe("2");
  });

  it("asterisco solto de conta não vira itálico", () => {
    const { container } = renderizar("Conta: 2 * 3 * 4");
    expect(container.querySelector("em")).toBeNull();
    expect(container.textContent).toBe("Conta: 2 * 3 * 4");
  });

  it("HTML vindo do modelo fica como texto", () => {
    const { container } = renderizar("<b>oi</b> <img src=x onerror=alert(1)>");
    expect(container.querySelector("b, img")).toBeNull();
    expect(container.textContent).toContain("<b>oi</b>");
  });

  it("mantém listas com hífen e o cursor no fim durante o streaming", () => {
    const { container } = renderizar("- um\n- dois", true);
    const itens = container.querySelectorAll("ul > li");
    expect(itens).toHaveLength(2);
    expect(itens[1].querySelector(".caret")).not.toBeNull();
  });
});
