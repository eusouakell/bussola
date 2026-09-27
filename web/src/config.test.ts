import { describe, expect, it } from "vitest";
import { CONFIG, lerConfig } from "./config";

describe("lerConfig", () => {
  it("sem variáveis, usa os padrões da demonstração", () => {
    expect(lerConfig({})).toMatchObject({
      modo: "simulado",
      app: "bussola_agent",
      login: false,
      usuarioAdk: "fernando",
      baseApi: "",
      anomesInicial: 202506,
      anomesFinal: 202512,
      atrasoSimuladoMs: 320,
      fatorLento: 6,
      limiteMensagemChars: 500,
      limiteSenhaChars: 128,
      raizDom: "root",
    });
  });

  it("lê o ambiente do Vite", () => {
    const config = lerConfig({
      VITE_BUSSOLA_MODO: "ao-vivo",
      VITE_ADK_APP: "outro_agent",
      VITE_ADK_USUARIO: "renata",
      VITE_BUSSOLA_LOGIN: "TRUE",
      VITE_BUSSOLA_API_BASE: "/bff",
      VITE_BUSSOLA_ANOMES_INICIAL: "202503",
      VITE_BUSSOLA_ANOMES_FINAL: "202510",
      VITE_BUSSOLA_ATRASO_MS: "50",
      VITE_BUSSOLA_LIMITE_MENSAGEM: "280",
    });
    expect(config).toMatchObject({
      modo: "ao-vivo",
      app: "outro_agent",
      usuarioAdk: "renata",
      login: true,
      baseApi: "/bff",
      anomesInicial: 202503,
      anomesFinal: 202510,
      atrasoSimuladoMs: 50,
      limiteMensagemChars: 280,
    });
  });

  it("valor inválido cai no padrão, sem derrubar o front", () => {
    // `anomes` fora de 202501–202512 (constituição III) e inteiros não positivos.
    const config = lerConfig({
      VITE_BUSSOLA_MODO: "qualquer",
      VITE_BUSSOLA_ANOMES_INICIAL: "202601",
      VITE_BUSSOLA_ANOMES_FINAL: "abc",
      VITE_BUSSOLA_ATRASO_MS: "-1",
      VITE_BUSSOLA_LIMITE_SENHA: "0",
      VITE_ADK_APP: "   ",
    });
    expect(config).toMatchObject({
      modo: "simulado",
      anomesInicial: 202506,
      anomesFinal: 202512,
      atrasoSimuladoMs: 320,
      limiteSenhaChars: 128,
      app: "bussola_agent",
    });
  });

  it("nenhum host absoluto nos padrões: o front fala com a própria origem (constituição VII)", () => {
    expect(JSON.stringify(CONFIG)).not.toMatch(/https?:\/\//);
  });
});
