// Configuração pública do front. Só modo e nome do app: nenhum segredo (constituição VII).
import type { Modo } from "./agente/transporte";

function modoInicial(valor: string | undefined): Modo {
  return valor === "ao-vivo" ? "ao-vivo" : "simulado";
}

export const CONFIG = {
  modo: modoInicial(import.meta.env.VITE_BUSSOLA_MODO),
  app: import.meta.env.VITE_ADK_APP || "bussola_agent",
  /** Usuário da sessão ADK (rótulo local; o `id_usuario` vem do ambiente do agente). */
  usuarioAdk: "fernando",
} as const;
