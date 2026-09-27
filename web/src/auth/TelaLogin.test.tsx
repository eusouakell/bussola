import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FalhaAuth, type Persona, type PortalAuth } from "./portal";
import { TelaLogin } from "./TelaLogin";

const PERSONAS: Persona[] = [
  { login: "fernando", displayName: "Fernando", summary: "Cliente âncora." },
  { login: "controle", displayName: "Renata", summary: "Persona de controle." },
];

/** Duplo do port: nenhuma instância de `ClienteAuth` e nenhum `vi.spyOn` na infra. */
function clienteCom(listar: () => Promise<Persona[]>): PortalAuth {
  return {
    listarPersonas: listar,
    sessaoAtual: () => Promise.resolve(null),
    entrar: () => Promise.reject(new Error("não usado")),
    sair: () => Promise.resolve(),
  };
}

describe("TelaLogin", () => {
  it("lista as personas, marca a primeira e entra com a escolhida", async () => {
    const onEntrar = vi.fn(() => Promise.resolve());
    render(<TelaLogin cliente={clienteCom(() => Promise.resolve(PERSONAS))} onEntrar={onEntrar} onModoSimulado={vi.fn()} />);

    expect(await screen.findByRole("radio", { name: /Fernando/ })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: /Renata/ }));
    await userEvent.type(screen.getByLabelText("Senha padrão de teste"), "senha-de-teste");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(onEntrar).toHaveBeenCalledWith("controle", "senha-de-teste");
  });

  it("mostra a mensagem do BFF e limpa a senha quando o login falha", async () => {
    const onEntrar = vi.fn(() => Promise.reject(new FalhaAuth("CREDENCIAIS_INVALIDAS", "Login ou senha inválidos.")));
    render(<TelaLogin cliente={clienteCom(() => Promise.resolve(PERSONAS))} onEntrar={onEntrar} onModoSimulado={vi.fn()} />);

    await screen.findByRole("radio", { name: /Fernando/ });
    const senha = screen.getByLabelText("Senha padrão de teste");
    await userEvent.type(senha, "errada-123");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Login ou senha inválidos.")).toBeInTheDocument();
    expect(senha).toHaveValue("");
  });

  it("sem personas por falha, oferece tentar de novo e o modo simulado", async () => {
    const listar = vi.fn<() => Promise<Persona[]>>().mockRejectedValueOnce(new FalhaAuth("REDE", "Sem conexão.")).mockResolvedValueOnce(PERSONAS);
    const onModoSimulado = vi.fn();
    render(<TelaLogin cliente={clienteCom(listar)} onEntrar={vi.fn()} onModoSimulado={onModoSimulado} />);

    expect(await screen.findByText("Sem conexão.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Tentar de novo/ }));
    expect(await screen.findByRole("radio", { name: /Fernando/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Usar modo simulado/ }));
    expect(onModoSimulado).toHaveBeenCalled();
  });
});
