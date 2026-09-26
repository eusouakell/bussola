// Varredura do bundle (T055, FR-028, SC-006, research R10). Roda depois do
// `vite build` (`npm run varrer`) e falha se `dist/` tiver UUID v4 completo,
// o projeto de nuvem, a âncora de usuário, SQL, chave do Google, chave
// privada PEM ou o nome do segredo do Gemini.
//
// O projeto e a âncora não ficam literais aqui: vêm de contracts/env.example
// em tempo de execução. Achados saem mascarados (nunca o valor inteiro).
//
// Uso: npx tsx scripts/varrer-bundle.ts [dir] [--env caminho/env.example]
import { existsSync, readdirSync, readFileSync, realpathSync, statSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));

export const DIR_DIST = resolve(AQUI, "..", "dist");
export const ENV_EXAMPLE = resolve(AQUI, "..", "..", "contracts", "env.example");

/** Arquivos de texto que o Vite pode emitir. Fontes e imagens binárias ficam de fora. */
export const EXTENSOES = new Set([".js", ".mjs", ".cjs", ".css", ".html", ".map", ".json", ".svg", ".txt", ".webmanifest"]);

export interface Padrao {
  nome: string;
  regex: RegExp;
}

export interface Achado {
  arquivo: string;
  linha: number;
  coluna: number;
  padrao: string;
  trecho: string;
}

// ------------------------------------------------------------ env.example

/** `CHAVE=valor` por linha; ignora comentários, aspas e comentário no fim da linha. */
export function lerEnv(texto: string): Record<string, string> {
  const saida: Record<string, string> = {};
  for (const bruta of texto.split(/\r?\n/)) {
    const linha = bruta.trim();
    if (!linha || linha.startsWith("#")) continue;
    const m = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(linha);
    if (!m) continue;
    let valor = m[2].trim();
    const aspas = /^(["'])(.*)\1$/.exec(valor);
    valor = aspas ? aspas[2] : valor.replace(/\s+#.*$/, "").trim();
    saida[m[1]] = valor;
  }
  return saida;
}

/** Valor vazio ou de exemplo (`<seu-projeto>`, `changeme`, `xxx`...) não vira padrão. */
export function ehPlaceholder(valor: string): boolean {
  const v = valor.trim();
  if (v.length < 6) return true;
  if (/^<.*>$|^\$\{.*\}$|^\.{3}$/.test(v)) return true;
  return /^(x+|changeme|change-me|todo|tbd|placeholder|none|null|seu[-_].*|sua[-_].*|meu[-_].*|your[-_].*|my[-_].*|exemplo.*|example.*)$/i.test(v);
}

/** Chaves do env.example que nomeiam o projeto de nuvem e a âncora de usuário. */
const CHAVE_PROJETO = /^(GOOGLE_CLOUD_PROJECT|GCLOUD_PROJECT|GCP_PROJECT|CLOUDSDK_CORE_PROJECT)(_ID)?$|(^|_)PROJECT_ID$/;
const CHAVE_ANCORA = /(^|_)ANCHOR(_|$)/;

export interface Sensiveis {
  projetos: string[];
  ancoras: string[];
}

export function extrairSensiveis(env: Record<string, string>): Sensiveis {
  const projetos = new Set<string>();
  const ancoras = new Set<string>();
  for (const [chave, valor] of Object.entries(env)) {
    if (ehPlaceholder(valor)) continue;
    if (CHAVE_PROJETO.test(chave)) projetos.add(valor);
    if (CHAVE_ANCORA.test(chave)) ancoras.add(valor);
  }
  return { projetos: [...projetos].sort(), ancoras: [...ancoras].sort() };
}

// ------------------------------------------------------------ padrões

function escapar(literal: string): string {
  return literal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Padrões fixos. SQL só em MAIÚSCULAS (convenção de contracts/bigquery e do
 * MCP) e com estrutura de comando: o React minificado usa `select`, `from`
 * e `Array.from` em minúsculas e sem espaço, então não dá falso positivo.
 */
export const PADROES_FIXOS: Padrao[] = [
  { nome: "UUID v4", regex: /(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}(?![0-9a-f])/gi },
  { nome: "SQL (SELECT … FROM)", regex: /\bSELECT\s+(?:DISTINCT\s+)?[^;]{1,300}?\sFROM\s+[\\`\w(]/g },
  { nome: "SQL (INSERT INTO)", regex: /\bINSERT\s+INTO\b/g },
  { nome: "SQL (DELETE/UPDATE/MERGE)", regex: /\bDELETE\s+FROM\b|\bUPDATE\s+[`\w.-]+\s+SET\b|\bMERGE\s+(?:INTO\s+)?[`\w.-]+\s+USING\b/g },
  { nome: "SQL (DDL)", regex: /\b(?:DROP|CREATE|ALTER|TRUNCATE)\s+(?:OR\s+REPLACE\s+)?(?:TABLE|SCHEMA|VIEW|DATABASE)\b/g },
  // `projeto-com-hifen.dataset.tabela` entre crases (escapadas ou não), como
  // no BigQuery. O minificador do Vite 8 escreve toda string entre crases, então
  // `react.element`, `bussola_dados.perfil_mensal` (fonte.tabelas) e rótulos
  // como `session.state.objetivo` são legítimos: só o nome com projeto conta.
  {
    nome: "SQL (tabela qualificada entre crases)",
    regex: /\\?`[a-z][a-z0-9]*(?:-[a-z0-9]+)+\.[A-Za-z_]\w*\.[A-Za-z_][\w-]*\\?`/g,
  },
  { nome: "chave do Google (AIza)", regex: /(?<![\w+/-])AIza[\w-]{30,}/g },
  { nome: "chave privada (-----BEGIN)", regex: /-----BEGIN/g },
  { nome: "nome de segredo (gemini-api-key)", regex: /gemini[-_]api[-_]key/gi },
];

export function montarPadroes(sensiveis: Sensiveis): Padrao[] {
  const padroes = [...PADROES_FIXOS];
  for (const projeto of sensiveis.projetos) {
    padroes.push({ nome: "projeto de nuvem (env.example)", regex: new RegExp(escapar(projeto), "gi") });
  }
  for (const ancora of sensiveis.ancoras) {
    padroes.push({ nome: "âncora de usuário (env.example)", regex: new RegExp(escapar(ancora), "gi") });
    const compacta = ancora.replace(/-/g, "");
    if (compacta !== ancora) {
      padroes.push({ nome: "âncora de usuário sem hífens (env.example)", regex: new RegExp(escapar(compacta), "gi") });
    }
  }
  return padroes;
}

// ------------------------------------------------------------ varredura

/** `36a21505-…` → `36a2…7269`: nunca o valor inteiro. */
export function mascarar(valor: string): string {
  const v = valor.replace(/\s+/g, " ");
  if (v.length <= 8) return `${v.slice(0, 2)}…`;
  return `${v.slice(0, 4)}…${v.slice(-4)}`;
}

interface Faixa {
  inicio: number;
  fim: number;
  padrao: string;
}

const JANELA = 16;

/** Vizinhança do achado; qualquer outro achado que caia nela também sai mascarado (`…`). */
function contexto(texto: string, alvo: Faixa, faixas: Faixa[]): string {
  const perto = faixas.filter((f) => f.fim > alvo.inicio - JANELA && f.inicio < alvo.fim + JANELA);
  const trecho = (de: number, ate: number) => {
    let saida = "";
    let mascarando = false;
    for (let i = Math.max(0, de); i < Math.min(texto.length, ate); i += 1) {
      const coberto = perto.some((f) => i >= f.inicio && i < f.fim);
      if (coberto && !mascarando) saida += "…";
      if (!coberto) saida += texto[i];
      mascarando = coberto;
    }
    return saida.replace(/\s+/g, " ");
  };
  return `${trecho(alvo.inicio - JANELA, alvo.inicio)}[${mascarar(texto.slice(alvo.inicio, alvo.fim))}]${trecho(alvo.fim, alvo.fim + JANELA)}`;
}

function posicao(texto: string, indice: number): { linha: number; coluna: number } {
  let linha = 1;
  let inicioLinha = 0;
  for (let i = texto.indexOf("\n"); i !== -1 && i < indice; i = texto.indexOf("\n", i + 1)) {
    linha += 1;
    inicioLinha = i + 1;
  }
  return { linha, coluna: indice - inicioLinha + 1 };
}

/** Varre um texto; `arquivo` só rotula os achados. */
export function varrerTexto(texto: string, arquivo: string, padroes: Padrao[]): Achado[] {
  const faixas: Faixa[] = [];
  for (const p of padroes) {
    const regex = new RegExp(p.regex.source, p.regex.flags.includes("g") ? p.regex.flags : `${p.regex.flags}g`);
    for (const m of texto.matchAll(regex)) {
      const inicio = m.index ?? 0;
      faixas.push({ inicio, fim: inicio + m[0].length, padrao: p.nome });
    }
  }
  return faixas
    .map((f) => ({ arquivo, ...posicao(texto, f.inicio), padrao: f.padrao, trecho: contexto(texto, f, faixas) }))
    .sort((a, b) => a.linha - b.linha || a.coluna - b.coluna || a.padrao.localeCompare(b.padrao));
}

/** Arquivos de texto de `dir`, recursivo e em ordem estável. */
export function listarArquivos(dir: string): string[] {
  const saida: string[] = [];
  for (const entrada of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const caminho = join(dir, entrada.name);
    if (entrada.isDirectory()) saida.push(...listarArquivos(caminho));
    else if (entrada.isFile() && EXTENSOES.has(extname(entrada.name).toLowerCase())) saida.push(caminho);
  }
  return saida;
}

export interface Resultado {
  arquivos: string[];
  achados: Achado[];
}

export function varrerDiretorio(dir: string, padroes: Padrao[]): Resultado {
  const arquivos = listarArquivos(dir);
  const achados = arquivos.flatMap((caminho) => varrerTexto(readFileSync(caminho, "utf8"), relative(dir, caminho), padroes));
  return { arquivos, achados };
}

// ------------------------------------------------------------ CLI

const MAX_LISTADOS = 50;

/** Caminho relativo ao cwd quando está dentro dele; absoluto nos outros casos. */
function legivel(caminho: string): string {
  const rel = relative(process.cwd(), caminho);
  if (!rel) return ".";
  return rel.startsWith("..") ? caminho : rel;
}

function lerArgs(argv: string[]): { dir: string; env: string } {
  let dir = DIR_DIST;
  let env = ENV_EXAMPLE;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--env" && argv[i + 1]) {
      env = resolve(argv[i + 1]);
      i += 1;
    } else {
      dir = resolve(argv[i]);
    }
  }
  return { dir, env };
}

export function main(argv: string[] = process.argv.slice(2)): number {
  const { dir, env } = lerArgs(argv);
  const rotulo = legivel(dir);

  if (!existsSync(dir) || !statSync(dir).isDirectory()) {
    console.error(`varrer-bundle: não encontrei ${rotulo}/. Rode \`npm run build\` (ou \`npx vite build\`) antes da varredura.`);
    return 1;
  }
  if (!existsSync(env)) {
    console.error(`varrer-bundle: não encontrei ${legivel(env)}; sem ele não sei o projeto nem a âncora a procurar.`);
    return 1;
  }

  const sensiveis = extrairSensiveis(lerEnv(readFileSync(env, "utf8")));
  if (sensiveis.projetos.length === 0 || sensiveis.ancoras.length === 0) {
    console.warn("varrer-bundle: aviso: env.example sem projeto ou sem âncora preenchidos; sigo só com os padrões fixos.");
  }

  const padroes = montarPadroes(sensiveis);
  const { arquivos, achados } = varrerDiretorio(dir, padroes);
  if (arquivos.length === 0) {
    console.error(`varrer-bundle: ${rotulo}/ não tem arquivos de texto (${[...EXTENSOES].join(", ")}). O build terminou?`);
    return 1;
  }

  if (achados.length > 0) {
    console.error(`varrer-bundle: FALHOU: ${achados.length} ocorrência(s) proibida(s) em ${rotulo}/ (FR-028):`);
    for (const a of achados.slice(0, MAX_LISTADOS)) {
      console.error(`  ${a.arquivo}:${a.linha}:${a.coluna}  ${a.padrao}  ${a.trecho}`);
    }
    if (achados.length > MAX_LISTADOS) console.error(`  … e mais ${achados.length - MAX_LISTADOS}.`);
    return 1;
  }

  console.log(
    `varrer-bundle: ok: ${arquivos.length} arquivo(s) em ${rotulo}/, sem segredo, SQL, projeto ou UUID completo (${padroes.length} padrões).`,
  );
  return 0;
}

function executadoDireto(): boolean {
  const entrada = process.argv[1];
  if (!entrada) return false;
  try {
    return realpathSync(resolve(entrada)) === realpathSync(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
}

if (executadoDireto()) process.exitCode = main();
