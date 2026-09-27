// Um turno do cliente: só texto, numa sessão do agente que pertence ao login.
// O `userId` do agente vem da sessão de login, nunca do corpo do pedido.
import type { AuthSession } from "../../domain/authSession.ts";
import { ChatMessage, MAX_CHAT_MESSAGE_CHARS } from "../../domain/chatMessage.ts";
import { NotFound } from "../errors.ts";
import type { AgentGateway } from "../ports/agentGateway.ts";

export interface SendMessageInput {
  sessionId: string;
  text: string;
}

export class SendMessage {
  private readonly agent: AgentGateway;
  private readonly maxChars: number;

  constructor(agent: AgentGateway, maxChars = MAX_CHAT_MESSAGE_CHARS) {
    this.agent = agent;
    this.maxChars = maxChars;
  }

  async execute(session: AuthSession, input: SendMessageInput, signal: AbortSignal): Promise<AsyncIterable<Uint8Array>> {
    if (!session.ownsAgentSession(input.sessionId)) throw new NotFound();
    const message = ChatMessage.create(input.text, this.maxChars);
    return this.agent.streamRun({ userId: session.account.login, sessionId: input.sessionId, message }, signal);
  }
}
