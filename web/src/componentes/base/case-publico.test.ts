import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const html = readFileSync("public/case/index.html", "utf8");
const document = new DOMParser().parseFromString(html, "text/html");

describe("Case Bússola V2 — publish-ready landing", () => {
  it("mantem estrutura semantica, navegacao e experiencia incorporada", () => {
    expect(document.documentElement.lang).toBe("pt-BR");
    expect(document.querySelectorAll("h1")).toHaveLength(1);

    for (const link of document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) {
      expect(document.getElementById(link.getAttribute("href")!.slice(1))).not.toBeNull();
    }

    for (const id of ["descoberta", "produto", "evolucao", "experimente", "pessoas"]) {
      expect(document.getElementById(id)).not.toBeNull();
    }

    expect(document.querySelector('#experimente iframe[title="Protótipo demonstrativo da Bússola"]')).not.toBeNull();
    expect(html).toContain("prefers-reduced-motion");
  });

  it("usa o hero aprovado como uma cena e nao volta a cards/flips como gramatica", () => {
    const fernando = document.querySelector<HTMLImageElement>('img[src="./assets/fernando-hero.webp"]');
    expect(fernando).not.toBeNull();
    expect(fernando!.alt.toLowerCase()).toContain("inteligência artificial");
    expect(existsSync("public/case/assets/fernando-hero.webp")).toBe(true);

    expect(document.querySelectorAll(".hero__ui")).toHaveLength(1);
    expect(document.querySelectorAll(".flip")).toHaveLength(0);
    expect(document.querySelectorAll(".phone")).toHaveLength(0);
    expect(html).not.toContain("backdrop-filter");
  });

  it("fundamenta a descoberta sem publicar percentuais retidos", () => {
    for (const termo of [
      "1.000 usuários",
      "SALDO",
      "POSITIVO",
      "USO DO",
      "ROTATIVO",
      "base sintética",
      "Gemini + ADK",
      "BigQuery",
      "Cloud Run",
      "Secret Manager",
    ]) {
      expect(html).toContain(termo);
    }

    expect(html).not.toContain("40,8%");
    expect(html).not.toContain("17 anos");
    expect(html).toContain("SEM PERCENTUAIS PÚBLICOS");
  });

  it("traz quatro comparacoes de UX sem esconder o antes/depois", () => {
    expect(document.querySelectorAll("#evolucao .craft-item")).toHaveLength(4);
    expect(document.querySelectorAll("#evolucao .compare")).toHaveLength(4);
    expect(document.querySelectorAll("#evolucao .ui-state")).toHaveLength(8);
    expect(html).toContain("RECONSTITUIÇÕES EDITORIAIS");
    expect(document.querySelectorAll("#evolucao input, #evolucao button")).toHaveLength(0);
  });

  it("mantem cinco retratos locais com contribuicoes e LinkedIn sempre visiveis", () => {
    const imagens = [...document.querySelectorAll<HTMLImageElement>("#pessoas .credit img")];
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

    expect(document.querySelectorAll("#pessoas a[href*='linkedin.com/in/']")).toHaveLength(5);
    expect(document.querySelectorAll("#pessoas button")).toHaveLength(0);
  });

  it("explicita provenance e os limites da PoC sem inflar maturidade", () => {
    expect(html).toContain("PERSONA NARRATIVA");
    expect(html).toContain("IMAGEM GERADA COM IA");
    expect(html).toContain("arquitetura de referência");
    expect(html).toContain("não está pronta para uso financeiro em produção");
    expect(html).toContain("testes assistivos completos");
    expect(html).toContain("agentes de IA");
    expect(html).not.toContain("IA agentiva");
  });
});
