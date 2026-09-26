// Formatação pt-BR (R9). Só muda a apresentação: nenhum valor novo é gerado aqui.
import type { Periodo } from "../agente/tipos";

const FUSO = "America/Sao_Paulo";

const moeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MESES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

/** `R$ 1.681,15` (BRL com 2 casas, como as ferramentas devolvem). */
export function brl(valor: number | null | undefined): string {
  if (typeof valor !== "number" || Number.isNaN(valor)) return "—";
  return moeda.format(valor);
}

/** Número pt-BR com casas fixas: `35,35`. */
export function numero(valor: number | null | undefined, casas = 0): string {
  if (typeof valor !== "number" || Number.isNaN(valor)) return "—";
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** Percentual que já vem em pontos (`35.35` → `35,35%`). */
export function percentual(valor: number | null | undefined, casas = 2): string {
  if (typeof valor !== "number" || Number.isNaN(valor)) return "—";
  return `${numero(valor, casas)}%`;
}

/** Fração exibida como percentual (`0.8` → `80%`): só mudança de escala. */
export function fracaoPercentual(valor: number | null | undefined): string {
  if (typeof valor !== "number" || Number.isNaN(valor)) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 0 }).format(valor);
}

function partes(anomes: number): { ano: number; mes: number } {
  return { ano: Math.floor(anomes / 100), mes: anomes % 100 };
}

/** `202507` → `jul/2025`. */
export function mesAbrev(anomes: number | null | undefined): string {
  if (typeof anomes !== "number") return "—";
  const { ano, mes } = partes(anomes);
  return `${MESES_ABREV[mes - 1] ?? "?"}/${ano}`;
}

/** `202507` → `julho de 2025`. */
export function mesExtenso(anomes: number | null | undefined): string {
  if (typeof anomes !== "number") return "—";
  const { ano, mes } = partes(anomes);
  return `${MESES[mes - 1] ?? "?"} de ${ano}`;
}

/** `202507` → `Julho`. */
export function nomeMes(anomes: number): string {
  const nome = MESES[partes(anomes).mes - 1] ?? "?";
  return nome.charAt(0).toUpperCase() + nome.slice(1);
}

/** `{inicio: 202501, fim: 202506}` → `jan–jun/2025`. */
export function periodo(p: Periodo | null | undefined): string {
  if (!p) return "—";
  if (p.inicio === p.fim) return mesAbrev(p.fim);
  const a = partes(p.inicio);
  const b = partes(p.fim);
  if (a.ano === b.ano) return `${MESES_ABREV[a.mes - 1]}–${MESES_ABREV[b.mes - 1]}/${b.ano}`;
  return `${mesAbrev(p.inicio)}–${mesAbrev(p.fim)}`;
}

function paraData(ts: number | string | Date): Date {
  if (ts instanceof Date) return ts;
  if (typeof ts === "number") return new Date(ts < 1e12 ? ts * 1000 : ts);
  return new Date(ts);
}

function campos(ts: number | string | Date, opcoes: Intl.DateTimeFormatOptions): Record<string, string> {
  const fmt = new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, hourCycle: "h23", ...opcoes });
  return Object.fromEntries(fmt.formatToParts(paraData(ts)).map((p) => [p.type, p.value]));
}

/** `26/09/2026 14:32`. Aceita segundos (ADK), milissegundos ou ISO. */
export function dataHora(ts: number | string | Date): string {
  const c = campos(ts, { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  return `${c.day}/${c.month}/${c.year} ${c.hour}:${c.minute}`;
}

/** `14:32`. */
export function hora(ts: number | string | Date): string {
  const c = campos(ts, { hour: "2-digit", minute: "2-digit" });
  return `${c.hour}:${c.minute}`;
}

/** `14:32:05`. */
export function horaSegundos(ts: number | string | Date): string {
  const c = campos(ts, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return `${c.hour}:${c.minute}:${c.second}`;
}

/** `18 meses`, `1 mês`. */
export function meses(n: number | null | undefined): string {
  if (typeof n !== "number") return "—";
  return n === 1 ? "1 mês" : `${numero(n)} meses`;
}

/** Máscara de identificador: `36a2…7269`. Nunca exibir o UUID completo. */
export function mascararId(id: string | null | undefined): string {
  if (!id) return "—";
  if (id.length <= 9) return id;
  return `${id.slice(0, 4)}…${id.slice(-4)}`;
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

function mascararValor(valor: unknown): unknown {
  if (typeof valor === "string") return valor.replace(UUID, (id) => mascararId(id));
  if (Array.isArray(valor)) return valor.map(mascararValor);
  if (valor && typeof valor === "object") return mascararArgs(valor as Record<string, unknown>);
  return valor;
}

/** Máscara recursiva de parâmetros exibidos nos Bastidores (objetos, listas e UUIDs dentro de textos). */
export function mascararArgs(args: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!args) return {};
  const saida: Record<string, unknown> = {};
  for (const [chave, valor] of Object.entries(args)) saida[chave] = mascararValor(valor);
  return saida;
}
