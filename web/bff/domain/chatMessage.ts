// Mensagem do cliente para o agente (value object): só texto, não vazio e com
// limite de tamanho. O front limita a 500; o BFF aceita até 2000.
import { DomainError } from "./errors.ts";

export const MAX_CHAT_MESSAGE_CHARS = 2000;

export class InvalidChatMessage extends DomainError {
  constructor() {
    super("mensagem vazia ou longa demais");
  }
}

export class ChatMessage {
  readonly text: string;

  private constructor(text: string) {
    this.text = text;
  }

  static create(text: string, maxChars = MAX_CHAT_MESSAGE_CHARS): ChatMessage {
    if (!text.trim() || text.length > maxChars) throw new InvalidChatMessage();
    return new ChatMessage(text);
  }
}
