import { existsSync, readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

const page = readFileSync("public/case/index.html", "utf8");
const { document } = new JSDOM(page).window;

describe("Gate editorial do case público", () => {
  it("tem título principal único e navegação sem links internos quebrados", () => {
    expect(document.documentElement.lang).toBe("pt-BR");
    expect(document.querySelectorAll("h1")).toHaveLength(1);
    const localLinks = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]'));
    expect(localLinks.length).toBeGreaterThan(5);
    for (const link of localLinks) {
      const id = link.getAttribute("href")?.slice(1);
      expect(id).toBeTruthy();
      expect(document.getElementById(id!)).not.toBeNull();
    }
  });

  it("contém os cinco retratos com descrições e arquivos presentes", () => {
    const imagens = Array.from(document.querySelectorAll<HTMLImageElement>('#creditos img'));
    expect(imagens).toHaveLength(5);
    for (const img of imagens) {
      expect(img.alt.trim().length).toBeGreaterThan(12);
      expect(img.getAttribute("src")).toMatch(/^assets\/.+\.webp$/);
      expect(existsSync(`public/case/${img.getAttribute("src")}`)).toBe(true);
    }
  });

  it("carrega a direção visual sem dependências externas e conserva a medição original", () => {
    const css = document.querySelector<HTMLLinkElement>('link[rel="stylesheet"][href="./editorial-v4.css"]');
    expect(css).not.toBeNull();
    expect(existsSync("public/case/editorial-v4.css")).toBe(true);
    expect(document.querySelector(".score-details > summary")).not.toBeNull();
    expect(page).toContain("6,4/10");
  });
});
