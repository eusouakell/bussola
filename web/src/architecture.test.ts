// @vitest-environment node
// Régua executável da regra de dependência do front, nos moldes de
// `web/bff/architecture.test.ts` (R4). Sem ela, A4 e A7 da varredura
// degradaram em silêncio: boas intenções não falham o CI.
//
// Direção permitida (cada camada só importa de si e das anteriores):
//
//   config ← contrato ← dominio ← aplicacao ← infra
//                                    ↑           ↑
//                                apresentacao ← bootstrap
//
// - `config`   configuração pública; folha, todo mundo pode importar.
// - `contrato` tipos do envelope ADK e o port `Transporte`. Sem dependências.
// - `dominio`  formatação pura (BRL, datas, máscaras).
// - `aplicacao` estado da sessão: reducer, auditoria, catálogo, sugestões.
// - `infra`    transportes (ADK e simulado) e o adapter HTTP do login.
// - `apresentacao` React: componentes, vistas, tela e hook de login.
// - `bootstrap` composition root (`App.tsx`, `main.tsx`).
//
// A regra que este arquivo existe para proteger: `apresentacao` e `aplicacao`
// NUNCA importam `infra` — em particular, nada de `simulado/` fora de `infra`.
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = import.meta.dirname;

type Camada = "config" | "contrato" | "dominio" | "aplicacao" | "infra" | "apresentacao" | "bootstrap";

const PERMITIDO: Record<Camada, readonly Camada[]> = {
  config: ["config", "contrato"],
  contrato: ["config", "contrato"],
  dominio: ["config", "contrato", "dominio"],
  aplicacao: ["config", "contrato", "dominio", "aplicacao"],
  infra: ["config", "contrato", "dominio", "aplicacao", "infra"],
  apresentacao: ["config", "contrato", "dominio", "aplicacao", "apresentacao"],
  bootstrap: ["config", "contrato", "dominio", "aplicacao", "infra", "apresentacao", "bootstrap"],
};

/** Camadas que não podem importar pacote nenhum (nem React, nem `node:`). */
const PURAS: readonly Camada[] = ["config", "contrato", "dominio", "aplicacao"];

/**
 * Arquivos cuja camada não sai do diretório. `agente/` e `auth/` guardam o
 * port e o adapter lado a lado, então a classificação é por arquivo.
 */
const POR_ARQUIVO: Record<string, Camada> = {
  "config.ts": "config",
  "App.tsx": "bootstrap",
  "main.tsx": "bootstrap",
  "agente/tipos.ts": "contrato",
  "agente/transporte.ts": "contrato",
  // Leitura do envelope `{dados, fonte, avisos}`: função pura sobre os tipos do
  // contrato, não transporte. Toda a apresentação depende dela.
  "agente/envelope.ts": "contrato",
  "auth/portal.ts": "contrato",
  "auth/clienteAuth.ts": "infra",
  // Hook React que liga o reducer puro ao ciclo de vida do componente. Fica na
  // apresentação para `aplicacao` continuar sem nenhum pacote (reducer,
  // auditoria e catálogo puros).
  "sessao/useSessao.ts": "apresentacao",
};

const POR_DIRETORIO: Record<string, Camada> = {
  formatacao: "dominio",
  sessao: "aplicacao",
  agente: "infra",
  simulado: "infra",
  auth: "apresentacao",
  componentes: "apresentacao",
  vistas: "apresentacao",
};

/**
 * Exceções conhecidas, `arquivo → especificador`. Vazio de propósito: uma
 * violação que não dá para zerar entra aqui **com o motivo**, e não afrouxando
 * a regra acima.
 */
const EXCECOES: Record<string, readonly string[]> = {};

const IMPORT =
  /(?:^|\s)(?:import|export)\s[^;]*?from\s+["']([^"']+)["']|(?:^|\s)import\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)/g;

function especificadores(fonte: string): string[] {
  return [...fonte.matchAll(IMPORT)].map((m) => m[1] ?? m[2] ?? m[3]);
}

function fontes(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entrada) => {
    const caminho = join(dir, entrada.name);
    if (entrada.isDirectory()) return entrada.name === "test" ? [] : fontes(caminho);
    const nome = entrada.name;
    if (!/\.tsx?$/.test(nome) || /\.test\.tsx?$/.test(nome) || nome.endsWith(".d.ts")) return [];
    return [caminho];
  });
}

function relativo(caminho: string): string {
  return relative(ROOT, caminho).split(sep).join("/");
}

function camadaDe(caminho: string): Camada | null {
  const nome = relativo(caminho);
  if (nome in POR_ARQUIVO) return POR_ARQUIVO[nome];
  const primeiro = nome.split("/")[0];
  return POR_DIRETORIO[primeiro] ?? null;
}

/** Resolve `./x` para o arquivo real (`x.ts`, `x.tsx` ou `x/index.ts`). */
function alvoDe(arquivo: string, especificador: string): string {
  const bruto = resolve(dirname(arquivo), especificador);
  for (const sufixo of ["", ".ts", ".tsx", "/index.ts", "/index.tsx"]) {
    const tentativa = `${bruto}${sufixo}`;
    if (ARQUIVOS.has(tentativa)) return tentativa;
  }
  return bruto;
}

const LISTA = fontes(ROOT);
const ARQUIVOS = new Set(LISTA);

describe("arquitetura do front", () => {
  it("todo arquivo de produção está numa camada conhecida", () => {
    expect(LISTA.length).toBeGreaterThan(40);
    expect(LISTA.filter((f) => camadaDe(f) === null).map(relativo)).toEqual([]);
  });

  it("cada camada só importa das camadas permitidas", () => {
    const violacoes: string[] = [];
    for (const arquivo of LISTA) {
      const camada = camadaDe(arquivo);
      if (!camada) continue;
      const nome = relativo(arquivo);
      for (const especificador of especificadores(readFileSync(arquivo, "utf-8"))) {
        if (EXCECOES[nome]?.includes(especificador)) continue;
        // Dados e estilo não são dependência de código.
        if (/\.(json|css)$/.test(especificador)) continue;
        if (!especificador.startsWith(".")) {
          if (PURAS.includes(camada)) violacoes.push(`${nome} importa o pacote ${especificador}`);
          continue;
        }
        const alvo = alvoDe(arquivo, especificador);
        if (!alvo.startsWith(ROOT + sep)) {
          violacoes.push(`${nome} importa fora de src/: ${especificador}`);
          continue;
        }
        const camadaAlvo = camadaDe(alvo);
        if (!camadaAlvo || !PERMITIDO[camada].includes(camadaAlvo)) {
          violacoes.push(`${nome} (${camada}) → ${especificador} (${camadaAlvo ?? "sem camada"})`);
        }
      }
    }
    expect(violacoes).toEqual([]);
  });

  it("só a infraestrutura conhece simulado/ (A4)", () => {
    const infratores = LISTA.filter((arquivo) => {
      if (camadaDe(arquivo) === "infra") return false;
      return especificadores(readFileSync(arquivo, "utf-8")).some((e) => /(^|\/)simulado\//.test(e));
    });
    expect(infratores.map(relativo)).toEqual([]);
  });

  it("o detector de imports enxerga import de tipo, de efeito, reexport e dinâmico", () => {
    const amostra = [
      'import type { A } from "../a";',
      'import {\n  B,\n  C,\n} from "react";',
      'export { D } from "./d";',
      'import "./efeito";',
      'const e = await import("./e");',
    ].join("\n");
    expect(especificadores(amostra)).toEqual(["../a", "react", "./d", "./efeito", "./e"]);
  });
});
