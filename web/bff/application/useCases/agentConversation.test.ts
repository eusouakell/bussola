// @vitest-environment node
// StartAgentSession, GetAgentSession e SendMessage: o id_usuario vem da conta
// e uma persona não usa a sessão do agente de outra.
import { describe, expect, it } from "vitest";
import { AuthSession } from "../../domain/authSession.ts";
import { InvalidChatMessage } from "../../domain/chatMessage.ts";
import { FakeAgentGateway, RecordingLogger } from "../../test/fakes.ts";
import { account } from "../../test/helpers.ts";
import { NotFound } from "../errors.ts";
import { GetAgentSession } from "./getAgentSession.ts";
import { SendMessage } from "./sendMessage.ts";
import { StartAgentSession } from "./startAgentSession.ts";

const policy = { idleTtlMs: 1000, absoluteTtlMs: 5000, maxAgentSessions: 2 };
const signal = new AbortController().signal;

function setup() {
  const agent = new FakeAgentGateway();
  const logger = new RecordingLogger();
  const fernando = new AuthSession("t1", account("fernando"), 0);
  const bianca = new AuthSession("t2", account("bianca"), 0);
  return {
    agent,
    logger,
    fernando,
    bianca,
    start: new StartAgentSession({ agent, policy, logger }),
    get: new GetAgentSession(agent),
    send: new SendMessage(agent, 50),
  };
}

describe("conversa com o agente", () => {
  it("cria a sessão só com o id_usuario da conta e registra a posse", async () => {
    const { agent, logger, fernando, start } = setup();
    const created = await start.execute(fernando);
    expect(agent.created).toEqual([{ userId: "fernando", state: { id_usuario: fernando.account.idUsuario } }]);
    expect(fernando.ownsAgentSession(created.id)).toBe(true);
    expect(logger.events()).toEqual(["sessao_criada"]);
  });

  it("lê e envia só na própria sessão; a de outra persona é NotFound", async () => {
    const { agent, fernando, bianca, start, get, send } = setup();
    const created = await start.execute(fernando);
    await expect(get.execute(fernando, created.id)).resolves.toMatchObject({ id: created.id });
    await expect(get.execute(bianca, created.id)).rejects.toThrow(NotFound);
    await expect(send.execute(bianca, { sessionId: created.id, text: "oi" }, signal)).rejects.toThrow(NotFound);
    expect(agent.turns).toHaveLength(0);
  });

  it("sessão registrada mas sumida do agente é NotFound", async () => {
    const { agent, fernando, start, get } = setup();
    const created = await start.execute(fernando);
    agent.sessions.clear();
    await expect(get.execute(fernando, created.id)).rejects.toThrow(NotFound);
  });

  it("envia o turno com o login da sessão e valida a mensagem", async () => {
    const { agent, fernando, start, send } = setup();
    const { id } = await start.execute(fernando);
    await send.execute(fernando, { sessionId: id, text: "quanto gastei?" }, signal);
    expect(agent.turns).toHaveLength(1);
    expect(agent.turns[0]).toMatchObject({ userId: "fernando", sessionId: id });
    expect(agent.turns[0].message.text).toBe("quanto gastei?");
    await expect(send.execute(fernando, { sessionId: id, text: "  " }, signal)).rejects.toThrow(InvalidChatMessage);
    await expect(send.execute(fernando, { sessionId: id, text: "a".repeat(51) }, signal)).rejects.toThrow(InvalidChatMessage);
  });
});
