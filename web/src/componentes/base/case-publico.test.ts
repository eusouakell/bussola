import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const html = readFileSync("public/case/index.html", "utf8");
const document = new DOMParser().parseFromString(html, "text/html");

describe("Case unificado V6 — narrativa visual e evidencias", () => {
  it("tem apenas um titulo principal e todas as ancoras locais resolvidas", () => {
    expect(document.documentElement.lang).toBe("pt-BR");
    expect(document.querySelectorAll("h1")).toHaveLength(1);
    for (const link of document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) {
      expect(document.getElementById(link.getAttribute("href")!.slice(1))).not.toBeNull();
    }
    expect(document.querySelector("#descoberta")).not.toBeNull();
    expect(document.querySelector("#evolucao")).not.toBeNull();
    expect(document.querySelector("#pessoas")).not.toBeNull();
    expect(document.querySelector('#experimente iframe[title]')).not.toBeNull();
  });

  it("traz quatro comparacoes em duas colunas de celular por secao", () => {
    expect(document.querySelectorAll(".proof > div")).toHaveLength(4);
    expect(document.querySelectorAll(".pair")).toHaveLength(4);
    expect(document.querySelectorAll(".pair .phone")).toHaveLength(8);
    expect(document.querySelectorAll(".compare-panel.after")).toHaveLength(4);
    expect(html).toContain("reconstituições editoriais");
  });

  it("fundamenta a descoberta em dados sinteticos e referencia a stack Google", () => {
    for (const termo of ["1.000", "BigQuery", "Gemini + ADK", "Cloud Run", "Secret Manager", "base sintética"]) {
      expect(html).toContain(termo);
    }
    expect(html).not.toContain("40,8%");
    expect(html).toContain("uso do rotativo do cartão mesmo sem saldo negativo");
  });

  it("mantem cinco fotos locais de equipe e mentora, com arquivos WebP validos", () => {
    const imagens = [...document.querySelectorAll<HTMLImageElement>("#pessoas img")];
    expect(imagens).toHaveLength(5);
    for (const img of imagens) {
      expect(img.alt.length).toBeGreaterThan(18);
      const src = img.getAttribute("src")!;
      expect(src).toMatch(/^\.\/assets\/.+\.webp$/);
      const p = `public/case/${src}`;
      expect(existsSync(p)).toBe(true);
      const buffer = readFileSync(p);
      expect(buffer.toString("ascii", 0, 4)).toBe("RIFF");
      expect(buffer.toString("ascii", 8, 12)).toBe("WEBP");
    }
    expect(document.querySelectorAll("#pessoas .flip button")).toHaveLength(4);
    expect(document.querySelectorAll("#pessoas a[href*='linkedin.com/in/']")).toHaveLength(5);
  });

  it("inclui Fernando gerado com IA e nao revela material interno do evento", () => {
    const img = document.querySelector<HTMLImageElement>('img[src="./assets/fernando-ai.png"]');
    expect(img).not.toBeNull();
    expect(img!.alt.toLowerCase()).toContain("inteligência artificial");
    expect(existsSync("public/case/assets/fernando-ai.png")).toBe(true);
    expect(html).not.toContain("Corporativo | Interno");
    expect(html).not.toContain("abaixo da média");
  });
});
