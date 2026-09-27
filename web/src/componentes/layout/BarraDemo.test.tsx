// A barra do apresentador escolhe qual conversa salva retomar (modo ao vivo).
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Modo, ResumoConversa } from "../../agente/transporte";
import { SEM_BORDAS } from "../../agente/transporte";
import { BarraDemo } from "./BarraDemo";

const CONVERSAS: ResumoConversa[] = [
  { sessionId: "s-9", atualizadaEm: Date.UTC(2026, 8, 20, 13, 45), titulo: "Viagem ao Japão" },
  { sessionId: "s-1", atualizadaEm: Date.UTC(2026, 8, 18, 9, 0) },
  { sessionId: "s-0" },
];

function montar(props: Partial<Parameters<typeof BarraDemo>[0]> = {}) {
  const onConversa = vi.fn();
  const onNovaConversa = vi.fn();
  render(
    <BarraDemo
      estado={{ estado_jornada: "OBJETIVO", ate_anomes: 202506 }}
      modo={"ao-vivo" as Modo}
      onModo={vi.fn()}
      onEnviar={vi.fn()}
      ocupado={false}
      bordas={SEM_BORDAS}
      onBordas={vi.fn()}
      persona={{ nome: "Fernando", onTrocar: vi.fn() }}
      conversas={CONVERSAS}
      conversaAtual="s-1"
      onConversa={onConversa}
      onNovaConversa={onNovaConversa}
      {...props}
    />,
  );
  return { onConversa, onNovaConversa };
}

function seletor(): HTMLSelectElement {
  return screen.getByLabelText("Conversa") as HTMLSelectElement;
}

describe("BarraDemo: conversas salvas", () => {
  it("lista as conversas na ordem recebida, com a aberta selecionada", () => {
    montar();
    expect(seletor().value).toBe("s-1");
    expect([...seletor().options].map((o) => o.value)).toEqual(["s-9", "s-1", "s-0"]);
  });

  it("rotula pelo objetivo, cai para a data e, sem horário, para a posição", () => {
    montar();
    const rotulos = [...seletor().options].map((o) => o.textContent);
    expect(rotulos[0]).toBe("Viagem ao Japão");
    expect(rotulos[1]).toMatch(/18/);
    expect(rotulos[2]).toBe("Conversa 3");
  });

  it("escolher outra conversa avisa uma vez, com o id dela", async () => {
    const { onConversa } = montar();
    await userEvent.selectOptions(seletor(), "s-9");
    expect(onConversa).toHaveBeenCalledExactlyOnceWith("s-9");
  });

  it("escolher a que já está aberta não faz nada", async () => {
    const { onConversa } = montar();
    await userEvent.selectOptions(seletor(), "s-1");
    expect(onConversa).not.toHaveBeenCalled();
  });

  it("conversa recém-criada, fora da lista salva, aparece como a atual", () => {
    montar({ conversaAtual: "s-nova" });
    expect(seletor().value).toBe("s-nova");
    expect(screen.getByRole("option", { name: "Conversa atual" })).toBeTruthy();
  });

  it("Nova conversa avisa o App; o seletor some quando não há nada salvo", async () => {
    const { onNovaConversa } = montar({ conversas: [] });
    expect(screen.queryByLabelText("Conversa")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Nova conversa" }));
    expect(onNovaConversa).toHaveBeenCalledOnce();
  });

  it("no simulado não há conversa salva para escolher", () => {
    montar({ modo: "simulado" as Modo });
    expect(screen.queryByLabelText("Conversa")).toBeNull();
    expect(screen.queryByRole("button", { name: "Nova conversa" })).toBeNull();
  });

  it("durante um turno, trocar de conversa fica travado", () => {
    montar({ ocupado: true });
    expect(seletor().disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Nova conversa" })).toHaveProperty("disabled", true);
  });
});
