// Montagem determinística de web/fixtures/ (contracts/fixtures-web.md).
import { readdirSync, readFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));

export const RAIZ_REPO = resolve(AQUI, "..", "..");
export const DIR_CONTRATOS = join(RAIZ_REPO, "contracts", "fixtures");
export const DIR_WEB_FIXTURES = resolve(AQUI, "..", "fixtures");

/** Ordena chaves recursivamente (equivalente a `sort_keys=True`). */
export function ordenar(valor: unknown): unknown {
  if (Array.isArray(valor)) return valor.map(ordenar);
  if (valor && typeof valor === "object") {
    const saida: Record<string, unknown> = {};
    for (const chave of Object.keys(valor).sort()) saida[chave] = ordenar((valor as Record<string, unknown>)[chave]);
    return saida;
  }
  return valor;
}

/** JSON com chaves ordenadas, 2 espaços e `\n` final. */
export function serializar(valor: unknown): string {
  return `${JSON.stringify(ordenar(valor), null, 2)}\n`;
}

function lerJson(caminho: string): unknown {
  return JSON.parse(readFileSync(caminho, "utf8"));
}

/** Conteúdo de `goldens.json` a partir de `contracts/fixtures/` (valores literais). */
export function montarGoldens(dir = DIR_CONTRATOS): unknown {
  const pasta = join(dir, "ferramentas");
  const ferramentas: Record<string, unknown> = {};
  for (const arquivo of readdirSync(pasta).filter((a) => a.endsWith(".json")).sort()) {
    ferramentas[basename(arquivo, ".json")] = lerJson(join(pasta, arquivo));
  }
  return {
    fonte: "contracts/fixtures",
    ferramentas,
    rag_trechos: lerJson(join(dir, "rag", "trechos_exemplo.json")),
  };
}
