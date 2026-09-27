// Configuração pública do front. Só modo, nome do app e o login do BFF:
// nenhum segredo (constituição VII).
import type { Modo } from "./agente/transporte";

function modoInicial(valor: string | undefined): Modo {
  return valor === "ao-vivo" ? "ao-vivo" : "simulado";
}

export const CONFIG = {
  modo: modoInicial(import.meta.env.VITE_BUSSOLA_MODO),
  app: import.meta.env.VITE_ADK_APP || "bussola_agent",
  /** `TRUE` quando o front é servido pelo BFF: o modo ao vivo exige login por persona. */
  login: import.meta.env.VITE_BUSSOLA_LOGIN === "TRUE",
  /** Usuário da sessão ADK (rótulo local; o `id_usuario` vem do ambiente do agente). */
  usuarioAdk: "fernando",
} as const;
