// @vitest-environment node
// Regra de dependência da Clean Architecture, verificada nos imports:
// domain ← application ← infrastructure | presentation ← main.
// Domínio e aplicação não usam `node:` nem pacotes: só código próprio.
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = import.meta.dirname;

type Layer = "domain" | "application" | "infrastructure" | "presentation" | "main" | "cli";

const ALLOWED: Record<Layer, readonly Layer[]> = {
  domain: ["domain"],
  application: ["domain", "application"],
  infrastructure: ["domain", "application", "infrastructure"],
  presentation: ["domain", "application", "presentation"],
  main: ["domain", "application", "infrastructure", "presentation", "main"],
  cli: ["infrastructure", "cli"],
};
const PURE: readonly Layer[] = ["domain", "application"];
const IMPORT =
  /(?:^|\s)(?:import|export)\s[^;]*?from\s+["']([^"']+)["']|(?:^|\s)import\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)/g;

function specifiers(source: string): string[] {
  return [...source.matchAll(IMPORT)].map((match) => match[1] ?? match[2] ?? match[3]);
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "test" ? [] : sourceFiles(path);
    return entry.name.endsWith(".ts") && !entry.name.endsWith(".test.ts") ? [path] : [];
  });
}

function layerOf(path: string): Layer | null {
  const first = relative(ROOT, path).split(sep)[0];
  return first in ALLOWED ? (first as Layer) : null;
}

function importsOf(path: string): string[] {
  return specifiers(readFileSync(path, "utf-8"));
}

const files = sourceFiles(ROOT);

describe("arquitetura do BFF", () => {
  it("todo arquivo de produção está numa camada conhecida", () => {
    expect(files.length).toBeGreaterThan(20);
    expect(files.filter((file) => layerOf(file) === null).map((file) => relative(ROOT, file))).toEqual([]);
  });

  it("cada camada só importa das camadas permitidas", () => {
    const violations: string[] = [];
    for (const file of files) {
      const layer = layerOf(file);
      if (!layer) continue;
      for (const specifier of importsOf(file)) {
        const name = relative(ROOT, file);
        if (!specifier.startsWith(".")) {
          if (PURE.includes(layer)) violations.push(`${name} importa ${specifier}`);
          continue;
        }
        const target = resolve(dirname(file), specifier);
        if (!target.startsWith(ROOT + sep)) {
          violations.push(`${name} importa fora do bff: ${specifier}`);
          continue;
        }
        const targetLayer = layerOf(target);
        if (!targetLayer || !ALLOWED[layer].includes(targetLayer)) violations.push(`${name} → ${specifier}`);
      }
    }
    expect(violations).toEqual([]);
  });

  it("o detector de imports enxerga import de tipo, de efeito, reexport e dinâmico", () => {
    const sample = [
      'import type { A } from "../a.ts";',
      'import {\n  B,\n  C,\n} from "node:fs";',
      'export { D } from "./d.ts";',
      'import "./efeito.ts";',
      'const e = await import("./e.ts");',
    ].join("\n");
    expect(specifiers(sample)).toEqual(["../a.ts", "node:fs", "./d.ts", "./efeito.ts", "./e.ts"]);
  });
});
