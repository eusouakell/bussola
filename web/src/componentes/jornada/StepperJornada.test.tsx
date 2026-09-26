import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StepperCompacto, StepperJornada, passosJornada } from "./StepperJornada";

describe("StepperJornada", () => {
  it("ORIENTAR → 3 passos concluídos, 1 atual e 2 futuros", () => {
    const passos = passosJornada("ORIENTAR");
    expect(passos.filter((p) => p.situacao === "done").map((p) => p.estado)).toEqual(["OBJETIVO", "ENTENDER", "ANTECIPAR"]);
    expect(passos.find((p) => p.situacao === "now")?.estado).toBe("ORIENTAR");
    expect(passos.filter((p) => p.situacao === "next")).toHaveLength(2);

    const { container } = render(<StepperJornada atual="ORIENTAR" />);
    expect(container.querySelectorAll(".wp.done")).toHaveLength(3);
    expect(container.querySelectorAll(".wp.now")).toHaveLength(1);
    expect(screen.getByRole("navigation", { name: "Jornada: Orientar" })).toBeTruthy();
  });

  it("sem estado começa em OBJETIVO", () => {
    expect(passosJornada(undefined)[0].situacao).toBe("now");
  });

  it("compacto mostra N/6 · Estado e abre as 6 etapas", () => {
    render(<StepperCompacto atual="AGIR" />);
    const botao = screen.getByRole("button", { name: /Jornada: Agir, etapa 5 de 6/ });
    expect(botao.textContent).toContain("5/6");
    fireEvent.click(botao);
    expect(screen.getByRole("list", { name: "Etapas da jornada" }).querySelectorAll("li")).toHaveLength(6);
  });
});
