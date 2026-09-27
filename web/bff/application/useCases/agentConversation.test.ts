// @vitest-environment node
// StartAgentSession, GetAgentSession, ListAgentSessions e SendMessage: o
// id_usuario vem da conta
// e uma persona não usa a sessão do agente de outra — quem recusa é o agente,
// que guarda a sessão sob o login, e não um registro na memória do BFF.
import { describe, expect, it } from "vitest";
import { AuthSession } from "../../domain/authSession.ts";
import { InvalidChatMessage } from "../../domain/chatMessage.ts";
import { FakeAgentGateway, RecordingLogger } from "../../test/fakes.ts";
import { account } from "../../test/helpers.ts";
import { NotFound } from "../errors.ts";
import { GetAgentSession } from "./getAgentSession.ts";
import { ListAgentSessions } from "./listAgentSessions.ts";
import { SendMessage } from "./sendMessage.ts";
import { StartAgentSession } from "./startAgentSession.ts";

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
    start: new StartAgentSession({ agent, logger }),
    get: new GetAgentSession(agent),
    list: new ListAgentSessions(agent),
    send: new SendMessage(agent, 50),
  };
}

describe("conversa com o agente", () => {
  it("cria a sessão só com o id_usuario da conta, sob o login", async () => {
    const { agent, logger, fernando, start } = setup();
    const created = await start.execute(fernando);
    expect(agent.created).toEqual([{ userId: "fernando", state: { id_usuario: fernando.account.idUsuario } }]);
    await expect(agent.getSession("fernando", created.id)).resolves.toMatchObject({ id: created.id });
    expect(logger.events()).toEqual(["sessao_criada"]);
  });

  it("um BFF reiniciado continua a conversa: a posse não mora na memória", async () => {
    const { agent, fernando, start, get, send } = setup();
    const { id } = await start.execute(fernando);
    // Outro processo, mesma sessão do agente: nada foi registrado localmente.
    const depois = new AuthSession("t3", account("fernando"), 0);
    await expect(get.execute(depois, id)).resolves.toMatchObject({ id });
    await send.execute(depois, { sessionId: id, text: "e agora?" }, signal);
    expect(agent.turns.at(-1)).toMatchObject({ userId: "fernando", sessionId: id });
  });

  it("lê e envia só na própria sessão; a de outra persona é NotFound", async () => {
    const { agent, fernando, bianca, start, get, send } = setup();
    const created = await start.execute(fernando);
    await expect(get.execute(fernando, created.id)).resolves.toMatchObject({ id: created.id });
    await expect(get.execute(bianca, created.id)).rejects.toThrow(NotFound);
    await expect(send.execute(bianca, { sessionId: created.id, text: "oi" }, signal)).rejects.toThrow(NotFound);
    expect(agent.turns).toHaveLength(0);
  });

  it("sessão que sumiu do agente é NotFound", async () => {
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

  it("lista as conversas da persona, da mais recente para a mais antiga e sem o histórico", async () => {
    const { fernando, bianca, start, list } = setup();
    const primeira = await start.execute(fernando);
    const segunda = await start.execute(fernando);
    await start.execute(bianca);
    const conversas = await list.execute(fernando);
    expect(conversas.map((c) => c.id)).toEqual([segunda.id, primeira.id]);
    // `events` é histórico: fica para o GET da conversa escolhida.
    for (const conversa of conversas) expect(conversa).not.toHaveProperty("events");
  });

  it("a lista de uma persona não traz a conversa de outra", async () => {
    const { fernando, bianca, start, list } = setup();
    const dela = await start.execute(bianca);
    await start.execute(fernando);
    const conversas = await list.execute(fernando);
    expect(conversas.map((c) => c.id)).not.toContain(dela.id);
    expect(JSON.stringify(conversas)).not.toContain(bianca.account.idUsuario);
  });
});
