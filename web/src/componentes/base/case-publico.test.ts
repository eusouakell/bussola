import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const page = readFileSync("public/case/index.html", "utf8");
const document = new DOMParser().parseFromString(page, "text/html");

describe("Case unificado V6 — UX / conteúdo / evidências", () => {
  it("mantém uma narrativa única e links de seção acessíveis", () => {
    expect(document.documentElement.lang).toBe("pt-BR");
    expect(document.querySelectorAll("h1")).toHaveLength(1);
    const links = [...document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')];
    expect(links.length).toBeGreaterThan(6);
    for (const link of links) {
      const id = link.getAttribute("href")?.slice(1);
      expect(id).toBeTruthy();
      expect(document.getElementById(id!)).not.toBeNull();
    }
    expect(document.querySelector("#pesquisa")).not.toBeNull();
    expect(document.querySelector("#telas")).not.toBeNull();
    expect(document.querySelector("#time")).not.toBeNull();
    expect(document.querySelector('#prototipo iframe[src="../"]')).not.toBeNull();
  });

  it("traz duas comparações visuais antes e depois em mockups de celular", () => {
    expect(document.querySelectorAll(".phone-row")).toHaveLength(2);
    expect(document.querySelectorAll(".phone-figure")).toHaveLength(4);
    expect(document.querySelectorAll(".phone-screen.before")).toHaveLength(2);
    expect(document.querySelectorAll(".phone-screen.after")).toHaveLength(2);
    expect(page).toContain("reconstituições visuais");
  });

  it("mostra amostra e distribuição como dados sintéticos e a stack Google documentada", () => {
    expect(page).toContain("1.000");
    expect(page).toContain("40,8%");
    expect(page).toContain("dados sintéticos");
    expect(page).toContain("ADK + Gemini");
    expect(page).toContain("BigQuery");
    expect(page).toContain("Cloud Run");
    expect(page).toContain("Secret Manager");
  });

  it("tem retratos locais e créditos profissionais com acesso por teclado", () => {
    const portraits = [...document.querySelectorAll<HTMLImageElement>("#time img")];
    expect(portraits).toHaveLength(5);
    for (const img of portraits) {
      const src = img.getAttribute("src");
      expect(img.alt.trim().length).toBeGreaterThan(10);
      expect(src).toMatch(/^assets\/.+\.webp$/);
      const path = `public/case/${src}`;
      expect(existsSync(path)).toBe(true);
      const binary = readFileSync(path);
      expect(binary.toString("ascii", 0, 4)).toBe("RIFF");
      expect(binary.toString("ascii", 8, 12)).toBe("WEBP");
      expect(binary.readUInt32LE(4) + 8).toBe(binary.byteLength);
    }
    expect(document.querySelectorAll(".person .flip")).toHaveLength(4);
    expect(document.querySelectorAll(".flip-back[inert]")).toHaveLength(4);
    expect(document.querySelectorAll(".person a[href*='linkedin.com/in/']")).toHaveLength(4);
    expect(document.querySelectorAll(".mentor a[href*='linkedin.com/in/']")).toHaveLength(1);
  });

  it("publica o Fernando gerado por IA com arquivo real e descrição precisa", () => {
    const figure = document.querySelector<HTMLImageElement>('.hero img[src="./assets/fernando-persona-ai.png"]');
    expect(figure).not.toBeNull();
    expect(figure?.alt).toContain("Imagem criada com IA");
    expect(existsSync("public/case/assets/fernando-persona-ai.png")).toBe(true);
  });

  it("não reintroduz azul dominante nem texto confidencial de avaliação", () => {
    expect(page).toContain(":root{--ink:#1c1c1e");
    // Azul permanece apenas na reconstrução visual da tela antiga.
    expect(page).not.toContain("Corporativo | Interno");
    expect(page).not.toContain("abaixo da média");
    expect(document.querySelector(".open-source details")).not.toBeNull();
  });
});
