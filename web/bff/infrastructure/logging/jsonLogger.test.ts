// @vitest-environment node
import { describe, expect, it } from "vitest";
import { exceptionName, type LogFields } from "../../application/ports/logger.ts";
import { jsonLogger } from "./jsonLogger.ts";

describe("jsonLogger", () => {
  it("emite uma linha JSON só com os campos permitidos", () => {
    const lines: string[] = [];
    const logger = jsonLogger((line) => lines.push(line));
    const fields = { evento: "login", id_usuario: "u1", password: "x", token: "t", texto: "mensagem" } as LogFields;

    logger.warn("teste", fields);

    expect(lines).toHaveLength(1);
    expect(lines[0].endsWith("\n")).toBe(true);
    const entry = JSON.parse(lines[0]);
    expect(Object.keys(entry).sort()).toEqual(["evento", "id_usuario", "message", "servico", "severity", "timestamp"]);
    expect(entry).toMatchObject({ severity: "WARNING", message: "teste", servico: "bussola-bff" });
  });

  it("exceção só pelo nome da classe", () => {
    expect(exceptionName(new TypeError("detalhe"))).toBe("TypeError");
    expect(exceptionName("texto")).toBe("string");
  });
});
