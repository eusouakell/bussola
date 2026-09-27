// Configuração pública do front: modo, endpoints, recorte da demonstração,
// limites e nomes fixos. Nenhum segredo (constituição VII).
//
// O que mora aqui: o que varia por ambiente ou deploy (modo, URLs e rotas,
// flags, limites, atrasos) e nomes fixos usados em mais de um módulo.
// O que NÃO mora aqui: copy ao cliente (`sessao/sugestoes-padrao.ts`,
// `sessao/catalogo.ts`, `simulado/textos.ts`), tipos de contrato
// (`agente/tipos.ts`) e códigos de erro do contrato. Copy é conteúdo.
import type { Modo } from "./agente/transporte";

/** Variáveis `VITE_*` lidas aqui. Todas opcionais: cada uma tem um padrão. */
export interface AmbienteFront {
  readonly VITE_BUSSOLA_MODO?: string;
  readonly VITE_ADK_APP?: string;
  readonly VITE_ADK_USUARIO?: string;
  readonly VITE_BUSSOLA_LOGIN?: string;
  readonly VITE_BUSSOLA_API_BASE?: string;
  readonly VITE_BUSSOLA_ANOMES_INICIAL?: string;
  readonly VITE_BUSSOLA_ANOMES_FINAL?: string;
  readonly VITE_BUSSOLA_ID_MASCARADO?: string;
  readonly VITE_BUSSOLA_ATRASO_MS?: string;
  readonly VITE_BUSSOLA_FATOR_LENTO?: string;
  readonly VITE_BUSSOLA_LIMITE_MENSAGEM?: string;
  readonly VITE_BUSSOLA_LIMITE_SENHA?: string;
}

/**
 * Ambiente do Vite. Fica vazio fora do navegador: os scripts com `tsx`
 * (`npm run fixtures`) importam o motor simulado, que chega até aqui.
 */
const ENV = (import.meta.env ?? {}) as AmbienteFront;

/** Janela de dados da PoC (constituição III: `ate_anomes` em 202501–202512). */
const ANOMES_MIN = 202501;
const ANOMES_MAX = 202512;

function modoDe(valor: string | undefined): Modo {
  return valor === "ao-vivo" ? "ao-vivo" : "simulado";
}

function flag(valor: string | undefined): boolean {
  return valor?.trim().toUpperCase() === "TRUE";
}

/** Texto não vazio ou o padrão (`VITE_*` ausente vira string vazia no build). */
function texto(valor: string | undefined, padrao: string): string {
  const limpo = valor?.trim();
  return limpo ? limpo : padrao;
}

/**
 * `anomes` de 202501 a 202512; fora da janela (ou não numérico) cai no padrão.
 * O front não tem log (constituição V), então a recusa é silenciosa.
 */
function anomes(valor: string | undefined, padrao: number): number {
  const n = Number(valor);
  return Number.isInteger(n) && n >= ANOMES_MIN && n <= ANOMES_MAX ? n : padrao;
}

/** Inteiro positivo ou o padrão. */
function inteiro(valor: string | undefined, padrao: number): number {
  const n = Number(valor);
  return Number.isInteger(n) && n > 0 ? n : padrao;
}

export function lerConfig(env: AmbienteFront) {
  return {
    modo: modoDe(env.VITE_BUSSOLA_MODO),
    app: texto(env.VITE_ADK_APP, "bussola_agent"),
    /** `TRUE` quando o front é servido pelo BFF: o modo ao vivo exige login por persona. */
    login: flag(env.VITE_BUSSOLA_LOGIN),
    /** Usuário da sessão ADK (rótulo local; o `id_usuario` vem do ambiente do agente). */
    usuarioAdk: texto(env.VITE_ADK_USUARIO, "fernando"),
    /** Prefixo das rotas do ADK e do BFF (vazio: mesma origem, com o proxy do Vite em dev). */
    baseApi: texto(env.VITE_BUSSOLA_API_BASE, ""),

    /** Primeiro e último mês do recorte gravado da demonstração. */
    anomesInicial: anomes(env.VITE_BUSSOLA_ANOMES_INICIAL, 202506),
    anomesFinal: anomes(env.VITE_BUSSOLA_ANOMES_FINAL, 202512),
    /** `id_usuario` já mascarado, exibido nos Bastidores antes do primeiro `stateDelta`. */
    idUsuarioMascarado: texto(env.VITE_BUSSOLA_ID_MASCARADO, "36a2…7269"),

    /** Rotas do ADK (contracts/eventos-agente.md §1). */
    rotasAdk: {
      apps: "/apps",
      runSse: "/run_sse",
    },
    /** Rotas de login no BFF (web/bff/presentation/http/router.ts). */
    rotasAuth: {
      personas: "/auth/personas",
      eu: "/auth/me",
      entrar: "/auth/login",
      sair: "/auth/logout",
    },

    /** Latência base do simulado no navegador. */
    atrasoSimuladoMs: inteiro(env.VITE_BUSSOLA_ATRASO_MS, 320),
    /** Multiplicador do atraso no cenário de borda E5 (resposta lenta). */
    fatorLento: inteiro(env.VITE_BUSSOLA_FATOR_LENTO, 6),

    /** Limites dos campos do front (o BFF revalida; `domain/chatMessage.ts`). */
    limiteMensagemChars: inteiro(env.VITE_BUSSOLA_LIMITE_MENSAGEM, 500),
    limiteSenhaChars: inteiro(env.VITE_BUSSOLA_LIMITE_SENHA, 128),

    /** `id` do elemento onde o React monta (`index.html`). */
    raizDom: "root",
  } as const;
}

export type Config = ReturnType<typeof lerConfig>;

export const CONFIG: Config = lerConfig(ENV);
