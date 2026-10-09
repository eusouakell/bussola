import { describe, expect, it } from "vitest";
import type { ModeloSessao } from "./modelo";
import { MODELO_INICIAL } from "./modelo";
import { sugestoesDoComposer } from "./sugestoes";

function modelo(plano_id?: string): ModeloSessao {
  return {
    ...MODELO_INICIAL,
    itens: [{ tipo: "mensagem_cliente", chave: "m1", ts: 0, texto: "Quero um plano" }],
    estado: { estado_jornada: "AGIR", plano_id },
  };
}

describe("Sugestões adequadas à etapa", () => {
  it("não sugere acompanhamento ou lembretes antes da criação do plano", () => {
    expect(sugestoesDoComposer(modelo(), "simulado")).toEqual([]);
    expect(sugestoesDoComposer(modelo(), "ao-vivo")).toEqual([]);
  });

  it("libera opções de acompanhamento quando existe um plano", () => {
    const opcoes = sugestoesDoComposer(modelo("plano-1"), "simulado");
    expect(opcoes).toContain("Ativar lembretes mensais");
  });
});
