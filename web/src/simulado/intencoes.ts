// Leitura de intenção do agente simulado: regras simples sobre o texto do
// cliente, só para ensaiar a jornada. O agente real usa o Gemini (ciclos 004–006).
import { CATALOGO } from "../sessao/catalogo";
import { normalizar } from "./guardrails";

export type TipoObjetivo = "imovel" | "viagem" | "educacao" | "dividas";

export type Intencao =
  | { tipo: "tentar_de_novo"; ferramenta: string }
  | { tipo: "objetivo"; objetivo: TipoObjetivo }
  | { tipo: "valores"; valor_alvo: number | null; prazo_meses: number | null }
  | { tipo: "nao_sei_valor" }
  | { tipo: "comparar" }
  | { tipo: "outro_caminho" }
  | { tipo: "aporte"; aporte_mensal: number }
  | { tipo: "escolher"; cenario: "conservador" | "equilibrado" | "acelerado" }
  | { tipo: "avancar_mes" }
  | { tipo: "adotar_rota"; rota: "A" | "B" | null }
  | { tipo: "lembretes" }
  | { tipo: "financiamento" }
  | { tipo: "duvida_credito" }
  | { tipo: "status" }
  | { tipo: "manter" }
  | { tipo: "diagnostico" }
  | { tipo: "continuar" }
  | { tipo: "novo_objetivo" }
  | { tipo: "ajuda" }
  | { tipo: "outro" };

export type RespostaConsentimento = "aceito" | "recusado" | "ambiguo";

const NUMEROS_POR_EXTENSO: Record<string, number> = { um: 1, uma: 1, dois: 2, duas: 2, tres: 3, quatro: 4, cinco: 5, seis: 6 };

/** `30.000` → 30000; `30,5` → 30.5; `2000` → 2000. */
function lerNumero(bruto: string): number {
  const semMilhar = /^\d{1,3}(\.\d{3})+(,\d+)?$/.test(bruto) ? bruto.replace(/\./g, "") : bruto;
  return Number(semMilhar.replace(",", "."));
}

function lerPrazo(t: string): { meses: number; resto: string } | null {
  const m = /\b(\d+|um|uma|dois|duas|tres|quatro|cinco|seis)\s*(anos?|meses|mes)\b/.exec(t);
  if (!m) return null;
  const n = NUMEROS_POR_EXTENSO[m[1]] ?? Number(m[1]);
  return { meses: m[2].startsWith("ano") ? n * 12 : n, resto: t.slice(0, m.index) + t.slice(m.index + m[0].length) };
}

/** Multiplicador do sufixo: `50 mil` → 50000; `100 milhoes` → 100000000 (BUG-03). */
const MULTIPLICADOR: Record<string, number> = { mil: 1000, k: 1000, milhao: 1e6, milhoes: 1e6, mi: 1e6 };

function lerValor(t: string): number | null {
  const m = /(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*(milhoes|milhao|mil|mi|k)?\b/.exec(t);
  if (!m) return null;
  const n = lerNumero(m[1]);
  return m[2] ? n * MULTIPLICADOR[m[2]] : n;
}

/** Resposta a um consentimento pendente (regra do ciclo 005). `null` = não é resposta. */
export function lerConsentimento(texto: string): RespostaConsentimento | null {
  const t = normalizar(texto);
  const negacao = /\b(nao|recuso|cancela\w*|nunca|negativo)\b/.test(t);
  const aceite = /\b(sim|pode|autorizo|ok|confirmo)\b/.test(t);
  const duvida = /\b(mas|talvez|depois|sera|duvida)\b|\?/.test(t);
  if (/\bnao sei\b/.test(t)) return "ambiguo";
  if (aceite && !negacao && !duvida) return "aceito";
  if (negacao && !aceite && !duvida) return "recusado";
  if (aceite || negacao || duvida) return t.split(" ").length <= 8 ? "ambiguo" : null;
  return null;
}

export function lerIntencao(texto: string): Intencao {
  const t = normalizar(texto);

  const retry = /^tentar de novo:\s*(.+)$/.exec(t);
  if (retry) {
    const alvo = Object.entries(CATALOGO).find(([, e]) => normalizar(e.legivel) === retry[1].trim());
    if (alvo) return { tipo: "tentar_de_novo", ferramenta: alvo[0] };
  }

  if (/\b(avanc\w* (um|1|o) mes|proximo mes|avancar)\b/.test(t)) return { tipo: "avancar_mes" };
  if (/\b(adot\w*|seguir|quero)\b.*\brota\b/.test(t)) {
    const rota = /\brota\s+([ab])\b/.exec(t);
    return { tipo: "adotar_rota", rota: rota ? (rota[1].toUpperCase() as "A" | "B") : null };
  }
  const cenario = /\b(conservador|equilibrado|acelerado)\b/.exec(t);
  if (cenario && /\b(quero|escolho|vou|prefiro|pode ser|fico)\b/.test(t)) {
    return { tipo: "escolher", cenario: cenario[1] as "conservador" | "equilibrado" | "acelerado" };
  }

  if (/\b(lembrete|lembretes)\b/.test(t)) return { tipo: "lembretes" };
  if (/\bsimul\w*\b.*\bfinanciamento\b/.test(t)) return { tipo: "financiamento" };
  if (/\b(status|como (esta|vai) (o )?meu plano|meu progresso)\b/.test(t)) return { tipo: "status" };
  if (/\bmanter o plano\b/.test(t)) return { tipo: "manter" };

  const prazo = lerPrazo(t);
  const porMes = /\b(por mes|ao mes|mensal\w*)\b|\/mes\b/.test(t);
  if (!prazo && porMes && /\b(guard\w*|apart\w*|aport\w*|poup\w*|junt\w*|separ\w*)\b/.test(t)) {
    const valor = lerValor(t);
    if (valor) return { tipo: "aporte", aporte_mensal: valor };
  }
  if (prazo) return { tipo: "valores", valor_alvo: lerValor(prazo.resto), prazo_meses: prazo.meses };
  if (/(r\$|\bmil\b|\bmilh\w+\b|\breais\b)/.test(t) && lerValor(t)) return { tipo: "valores", valor_alvo: lerValor(t), prazo_meses: null };
  if (/\bnao sei\b/.test(t)) return { tipo: "nao_sei_valor" };

  if (/\b(caminhos?|cenarios?|opcoes|compar\w*)\b/.test(t)) {
    return /\boutro caminho\b/.test(t) ? { tipo: "outro_caminho" } : { tipo: "comparar" };
  }

  if (/\b(apartamento|imovel|casa propria|entrada)\b/.test(t)) return { tipo: "objetivo", objetivo: "imovel" };
  if (/\b(viaj\w*|viagem|ferias)\b/.test(t)) return { tipo: "objetivo", objetivo: "viagem" };
  if (/\b(pos|pos-graduacao|mba|curso|faculdade|especializacao)\b/.test(t)) return { tipo: "objetivo", objetivo: "educacao" };
  if (/\b(dividas?|parcelas?|endividad\w*)\b/.test(t)) return { tipo: "objetivo", objetivo: "dividas" };

  // BUG-02: pergunta legítima sobre crédito que não é promessa de aprovação.
  if (/\b(emprestimos?|credito|financiamentos?|financiar|juros|cet|consignado|cheque especial|rotativo)\b/.test(t)) {
    return { tipo: "duvida_credito" };
  }

  if (/\b(outro|novo) objetivo\b/.test(t)) return { tipo: "novo_objetivo" };
  if (/\b(diagnostico|refaz\w*|meus gastos|perfil)\b/.test(t)) return { tipo: "diagnostico" };
  if (/\bcontinuar\b/.test(t)) return { tipo: "continuar" };
  if (/\b(ajuda|o que (voce )?(pode|consegue) fazer)\b/.test(t)) return { tipo: "ajuda" };
  return { tipo: "outro" };
}
