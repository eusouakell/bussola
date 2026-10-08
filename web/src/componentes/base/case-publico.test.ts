import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const page = readFileSync("public/case/index.html", "utf8");
const pageDocument = new DOMParser().parseFromString(page, "text/html");

describe("Gate editorial do case público", () => {
  it("tem título principal único e navegação sem links internos quebrados", () => {
    expect(pageDocument.documentElement.lang).toBe("pt-BR");
    expect(pageDocument.querySelectorAll("h1")).toHaveLength(1);
    const localLinks = Array.from(pageDocument.querySelectorAll<HTMLAnchorElement>('a[href^="#"]'));
    expect(localLinks.length).toBeGreaterThan(5);
    for (const link of localLinks) {
      const id = link.getAttribute("href")?.slice(1);
      expect(id).toBeTruthy();
      expect(pageDocument.getElementById(id!)).not.toBeNull();
    }
  });

  it("contém os cinco retratos com descrições e arquivos presentes", () => {
    const imagens = Array.from(pageDocument.querySelectorAll<HTMLImageElement>('#creditos img'));
    expect(imagens).toHaveLength(5);
    for (const img of imagens) {
      expect(img.alt.trim().length).toBeGreaterThan(12);
      expect(img.getAttribute("src")).toMatch(/^assets\/.+\.webp$/);
      expect(existsSync(`public/case/${img.getAttribute("src")}`)).toBe(true);
    }
  });

  it("carrega a direção visual sem dependências externas e conserva a medição original", () => {
    const css = pageDocument.querySelector<HTMLLinkElement>('link[rel="stylesheet"][href="./editorial-v4.css"]');
    expect(css).not.toBeNull();
    expect(existsSync("public/case/editorial-v4.css")).toBe(true);
    expect(pageDocument.querySelector(".score-details > summary")).not.toBeNull();
    expect(page).toContain("6,4/10");
  });
});
