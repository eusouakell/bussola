// @vitest-environment node
import { describe, expect, it } from "vitest";
import { AgentUnavailable, InvalidCredentials, NotAuthenticated, NotFound, TooManyAttempts } from "../../application/errors.ts";
import { InvalidChatMessage } from "../../domain/chatMessage.ts";
import { RecordingLogger } from "../../test/fakes.ts";
import { HttpError, toHttpError } from "./httpErrors.ts";

describe("toHttpError", () => {
  it.each([
    [new InvalidChatMessage(), 400, "PEDIDO_INVALIDO"],
    [new InvalidCredentials(), 401, "CREDENCIAIS_INVALIDAS"],
    [new NotAuthenticated(), 401, "NAO_AUTENTICADO"],
    [new NotFound(), 404, "NAO_ENCONTRADO"],
    [new TooManyAttempts(), 429, "MUITAS_TENTATIVAS"],
    [new HttpError(415, "TIPO_NAO_SUPORTADO", "x"), 415, "TIPO_NAO_SUPORTADO"],
  ])("%s → %i %s, sem log", (error, status, code) => {
    const logger = new RecordingLogger();
    expect(toHttpError(error, logger)).toMatchObject({ status, code });
    expect(logger.entries).toEqual([]);
  });

  it("agente indisponível vira 502 e loga só o código", () => {
    const logger = new RecordingLogger();
    expect(toHttpError(new AgentUnavailable("HTTP_500"), logger)).toMatchObject({ status: 502, code: "AGENTE_INDISPONIVEL" });
    expect(logger.entries).toEqual([
      { level: "warn", message: "agente indisponível", evento: "agente_indisponivel", erro_codigo: "HTTP_500" },
    ]);
  });

  it("erro inesperado vira 503 genérico e loga só o nome da exceção", () => {
    const logger = new RecordingLogger();
    const failure = toHttpError(new TypeError("segredo no detalhe"), logger);
    expect(failure).toMatchObject({ status: 503, code: "INDISPONIVEL" });
    expect(failure.message).not.toContain("segredo");
    expect(JSON.stringify(logger.entries)).not.toContain("segredo");
    expect(logger.entries[0]).toMatchObject({ evento: "erro_interno", excecao: "TypeError" });
  });
});
