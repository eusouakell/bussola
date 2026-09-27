// @vitest-environment node
import { describe, expect, it } from "vitest";
import { ChatMessage, InvalidChatMessage, MAX_CHAT_MESSAGE_CHARS } from "./chatMessage.ts";

describe("ChatMessage", () => {
  it("aceita texto até o limite, sem alterar", () => {
    expect(ChatMessage.create("  quanto gastei?  ").text).toBe("  quanto gastei?  ");
    expect(ChatMessage.create("a".repeat(MAX_CHAT_MESSAGE_CHARS)).text).toHaveLength(MAX_CHAT_MESSAGE_CHARS);
  });

  it.each(["", "   ", "\n\t", "a".repeat(MAX_CHAT_MESSAGE_CHARS + 1)])("recusa vazio ou longo demais (%#)", (text) => {
    expect(() => ChatMessage.create(text)).toThrow(InvalidChatMessage);
  });

  it("respeita limite menor", () => {
    expect(() => ChatMessage.create("abcdef", 5)).toThrow(InvalidChatMessage);
  });
});
