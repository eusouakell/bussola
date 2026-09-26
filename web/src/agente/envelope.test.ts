import { describe, expect, it } from "vitest";
import { extrairEnvelope } from "./envelope";

const envelope = {
  dados: { sobra_mediana: 1729.0 },
  fonte: { ferramenta: "capacidade_poupanca", tabelas: ["bussola_dados.perfil_mensal"] },
  avisos: [],
};

describe("extrairEnvelope", () => {
  it("aceita o envelope direto", () => {
    expect(extrairEnvelope(envelope)).toEqual({ tipo: "envelope", envelope });
  });

  it("aceita {result}", () => {
    expect(extrairEnvelope({ result: envelope })).toEqual({ tipo: "envelope", envelope });
  });

  it("aceita structuredContent e structuredContent.result", () => {
    expect(extrairEnvelope({ structuredContent: envelope })).toEqual({ tipo: "envelope", envelope });
    expect(extrairEnvelope({ structuredContent: { result: envelope } })).toEqual({ tipo: "envelope", envelope });
  });

  it("aceita content[].text com JSON", () => {
    const resposta = { content: [{ type: "text", text: JSON.stringify(envelope) }], isError: false };
    expect(extrairEnvelope(resposta)).toEqual({ tipo: "envelope", envelope });
  });

  it("devolve o código de erro sem a mensagem técnica", () => {
    const resposta = { result: { erro: { codigo: "INDISPONIVEL", mensagem: "detalhe técnico" } } };
    expect(extrairEnvelope(resposta)).toEqual({ tipo: "erro", codigo: "INDISPONIVEL" });
  });

  it("erro do MCP em texto livre (isError) vira INDISPONIVEL, sem o texto", () => {
    const texto = { content: [{ type: "text", text: "Traceback: tempo esgotado" }], isError: true };
    expect(extrairEnvelope(texto)).toEqual({ tipo: "erro", codigo: "INDISPONIVEL" });
    expect(extrairEnvelope({ result: texto })).toEqual({ tipo: "erro", codigo: "INDISPONIVEL" });
  });

  it("trata o resto como dados crus", () => {
    expect(extrairEnvelope({ plano_id: "p-1" })).toEqual({ tipo: "cru", dados: { plano_id: "p-1" } });
    expect(extrairEnvelope("texto")).toEqual({ tipo: "cru", dados: {} });
    expect(extrairEnvelope({ content: [{ type: "text", text: "não é json" }] }).tipo).toBe("cru");
  });
});
