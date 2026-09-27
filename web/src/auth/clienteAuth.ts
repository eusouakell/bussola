// Adapter HTTP do port `PortalAuth` contra o BFF (`web/bff`): lista de
// personas, login, sessão atual e logout. A sessão fica num cookie HttpOnly que
// o navegador manda sozinho; o front só conhece o `login` da persona, nunca o
// `id_usuario`.
import { CONFIG } from "../config";
import { FalhaAuth, type Persona, type PortalAuth } from "./portal";

const MENSAGEM_PADRAO = "Não foi possível falar com o servidor. Tente de novo.";

export interface OpcoesAuth {
  /** Prefixo das rotas (padrão: `CONFIG.baseApi`, vazio no mesmo host do BFF). */
  base?: string;
  fetch?: typeof fetch;
}

function ehPersona(valor: unknown): valor is Persona {
  if (typeof valor !== "object" || valor === null) return false;
  const p = valor as Record<string, unknown>;
  return typeof p.login === "string" && typeof p.displayName === "string" && typeof p.summary === "string";
}

export class ClienteAuth implements PortalAuth {
  private readonly opcoes: OpcoesAuth;

  constructor(opcoes: OpcoesAuth = {}) {
    this.opcoes = opcoes;
  }

  private async buscar(caminho: string, init?: RequestInit): Promise<Response> {
    const f = this.opcoes.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
    try {
      return await f(`${this.opcoes.base ?? CONFIG.baseApi}${caminho}`, { credentials: "same-origin", ...init });
    } catch {
      throw new FalhaAuth("REDE", MENSAGEM_PADRAO);
    }
  }

  private async falha(resposta: Response): Promise<FalhaAuth> {
    try {
      const corpo = (await resposta.json()) as { erro?: { codigo?: unknown; mensagem?: unknown } };
      const { codigo, mensagem } = corpo.erro ?? {};
      if (typeof codigo === "string" && typeof mensagem === "string") return new FalhaAuth(codigo, mensagem);
    } catch {
      // Sem envelope: mensagem padrão.
    }
    return new FalhaAuth(`HTTP_${resposta.status}`, MENSAGEM_PADRAO);
  }

  private async persona(resposta: Response): Promise<Persona> {
    const corpo = (await resposta.json().catch(() => null)) as { usuario?: unknown } | null;
    if (!ehPersona(corpo?.usuario)) throw new FalhaAuth("RESPOSTA_INVALIDA", MENSAGEM_PADRAO);
    return corpo.usuario;
  }

  async listarPersonas(): Promise<Persona[]> {
    const resposta = await this.buscar(CONFIG.rotasAuth.personas);
    if (!resposta.ok) throw await this.falha(resposta);
    const corpo = (await resposta.json().catch(() => null)) as { personas?: unknown } | null;
    if (!Array.isArray(corpo?.personas)) throw new FalhaAuth("RESPOSTA_INVALIDA", MENSAGEM_PADRAO);
    return corpo.personas.filter(ehPersona);
  }

  /** Persona logada ou `null` sem sessão (401). */
  async sessaoAtual(): Promise<Persona | null> {
    const resposta = await this.buscar(CONFIG.rotasAuth.eu);
    if (resposta.status === 401) return null;
    if (!resposta.ok) throw await this.falha(resposta);
    return this.persona(resposta);
  }

  async entrar(login: string, senha: string): Promise<Persona> {
    const resposta = await this.buscar(CONFIG.rotasAuth.entrar, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, password: senha }),
    });
    if (!resposta.ok) throw await this.falha(resposta);
    return this.persona(resposta);
  }

  async sair(): Promise<void> {
    const resposta = await this.buscar(CONFIG.rotasAuth.sair, { method: "POST" });
    if (!resposta.ok) throw await this.falha(resposta);
  }
}
