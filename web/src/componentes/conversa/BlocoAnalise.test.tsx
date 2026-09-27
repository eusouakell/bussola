import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ItemFerramenta } from "../../sessao/modelo";
import { BlocoAnalise } from "./BlocoAnalise";

const COPY_DADOS = "Tenho poucos meses de histórico para estimar sua sobra com segurança.";

function item(nome: string, codigo?: string): ItemFerramenta {
  return {
    tipo: "ferramenta",
    chave: `f-${nome}`,
    ts: 0,
    chamadaId: `c-${nome}`,
    nome,
    args: {},
    status: codigo ? "erro" : "ok",
    resposta: codigo ? { tipo: "erro", codigo } : undefined,
    inicio: 0,
    turno: 1,
  };
}

async function abrir(nome: RegExp) {
  await userEvent.setup().click(screen.getByRole("button", { name: nome }));
}

describe("BlocoAnalise: erros agrupados por mensagem (BUG-05b)", () => {
  it("várias ferramentas com o mesmo código mostram a frase uma vez só", async () => {
    const itens = ["dividas_e_parcelas", "oportunidades_corte", "resumo_mes"].map((n) => item(n, "DADOS_INSUFICIENTES"));
    render(<BlocoAnalise itens={[...itens, item("perfil_financeiro", "DADOS_INSUFICIENTES")]} onEnviar={vi.fn()} ocupado={false} />);
    const notas = screen.getAllByRole("note");
    expect(notas).toHaveLength(1);
    expect(notas[0]).toHaveTextContent(COPY_DADOS);
    expect(screen.getAllByText(COPY_DADOS)).toHaveLength(1);

    // quais ferramentas falharam continua visível na lista
    await abrir(/Analisei sua situação · 4 consultas/);
    expect(screen.getAllByRole("img", { name: "Falhou" })).toHaveLength(3);
    expect(screen.getAllByRole("img", { name: "Com ressalva" })).toHaveLength(1);
  });

  it("mensagens diferentes continuam separadas, uma por ferramenta", async () => {
    render(
      <BlocoAnalise
        itens={[item("dividas_e_parcelas", "INDISPONIVEL"), item("oportunidades_corte", "INDISPONIVEL"), item("resumo_mes")]}
        onEnviar={vi.fn()}
        ocupado={false}
      />,
    );
    const alertas = screen.getAllByRole("alert", { name: "ErroFerramenta" });
    expect(alertas).toHaveLength(2);
    expect(alertas[0]).toHaveTextContent("Não consegui consultar dívidas e parcelas agora.");
    expect(alertas[1]).toHaveTextContent("Não consegui consultar oportunidades de corte agora.");
    await abrir(/Analisei sua situação · 3 consultas/);
    expect(screen.getAllByRole("img", { name: "Falhou" })).toHaveLength(2);
  });

  it("erro escondido na conversa não vira aviso nenhum", () => {
    render(
      <BlocoAnalise
        itens={[item("perfil_financeiro", "DADOS_INSUFICIENTES"), item("capacidade_poupanca", "DADOS_INSUFICIENTES")]}
        onEnviar={vi.fn()}
        ocupado={false}
      />,
    );
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
