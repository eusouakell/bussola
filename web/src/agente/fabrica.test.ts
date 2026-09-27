import { describe, expect, it } from "vitest";
import { AgenteSimulado } from "../simulado/agente-simulado";
import { criarTransporte } from "./fabrica";
import { ClienteAdk } from "./cliente-adk";

describe("criarTransporte", () => {
  it("escolhe o transporte pelo modo", () => {
    expect(criarTransporte("ao-vivo")).toBeInstanceOf(ClienteAdk);
    expect(criarTransporte("simulado")).toBeInstanceOf(AgenteSimulado);
  });

  it("o simulado nasce com as bordas pedidas e o ao vivo não implementa o método", () => {
    const simulado = criarTransporte("simulado", { e3: true, e4: false, e5: true });
    expect(simulado.configurarBordas).toBeTypeOf("function");
    expect((simulado as AgenteSimulado).bordas).toEqual({ e3: true, e4: false, e5: true });
    expect(criarTransporte("ao-vivo").configurarBordas).toBeUndefined();
  });

  it("sem bordas, nenhum cenário de borda fica ligado", () => {
    expect((criarTransporte("simulado") as AgenteSimulado).bordas).toEqual({ e3: false, e4: false, e5: false });
  });
});
