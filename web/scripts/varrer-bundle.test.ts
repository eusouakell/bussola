import { describe, expect, it } from "vitest";
import { extrairSensiveis, lerEnv, mascarar, montarPadroes, PADROES_FIXOS, varrerTexto } from "./varrer-bundle";

const padroes = PADROES_FIXOS;
const nomes = (texto: string) => varrerTexto(texto, "x.js", padroes).map((a) => a.padrao);

describe("varrer-bundle", () => {
  it("strings do bundle minificado entre crases não são SQL", () => {
    expect(nomes("c=Symbol.for(`react.element`);")).toEqual([]);
    expect(nomes("tabelas:[`bussola_dados.perfil_mensal`],periodo:{}")).toEqual([]);
    expect(nomes("children:[`session.state.objetivo`]")).toEqual([]);
    expect(nomes("n=Array.from(e).select(t)")).toEqual([]);
  });

  it("acha tabela com projeto entre crases, escapadas ou não", () => {
    expect(nomes("q=`meu-proj-01.bussola_dados.perfil_mensal`")).toEqual(["SQL (tabela qualificada entre crases)"]);
    expect(nomes('q="\\`meu-proj-01.ds.t\\`"')).toEqual(["SQL (tabela qualificada entre crases)"]);
  });

  it("acha comandos SQL em maiúsculas", () => {
    expect(nomes("`SELECT id FROM t`")).toContain("SQL (SELECT … FROM)");
    expect(nomes("DELETE FROM x")).toContain("SQL (DELETE/UPDATE/MERGE)");
    expect(nomes("CREATE OR REPLACE TABLE x")).toContain("SQL (DDL)");
  });

  it("acha UUID v4, chave do Google e nome do segredo", () => {
    expect(nomes("id:`0b6f5c1e-3a2d-4c7b-9e8f-1a2b3c4d5e6f`")).toEqual(["UUID v4"]);
    expect(nomes(`k="AIza${"a".repeat(35)}"`)).toEqual(["chave do Google (AIza)"]);
    expect(nomes("s=`gemini-api-key`")).toEqual(["nome de segredo (gemini-api-key)"]);
  });

  it("projeto e âncora vêm do env.example, e o achado sai mascarado", () => {
    const env = lerEnv("GOOGLE_CLOUD_PROJECT=projeto-teste-99\nANCHOR_USER_ID=0b6f5c1e-3a2d-4c7b-9e8f-1a2b3c4d5e6f\nX=<seu-projeto>\n");
    const sensiveis = extrairSensiveis(env);
    expect(sensiveis.projetos).toEqual(["projeto-teste-99"]);
    const achados = varrerTexto("p=`projeto-teste-99`;a=`0b6f5c1e3a2d4c7b9e8f1a2b3c4d5e6f`", "x.js", montarPadroes(sensiveis));
    expect(achados.map((a) => a.padrao)).toEqual(["projeto de nuvem (env.example)", "âncora de usuário sem hífens (env.example)"]);
    expect(achados.every((a) => !a.trecho.includes("projeto-teste-99") && !a.trecho.includes("0b6f5c1e3a2d"))).toBe(true);
    expect(mascarar("0b6f5c1e-3a2d-4c7b-9e8f-1a2b3c4d5e6f")).toBe("0b6f…5e6f");
  });
});
