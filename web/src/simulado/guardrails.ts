// Guardrails do agente simulado (E1, E2). Espelham as regras do ciclo 005:
// o agente real decide no servidor; aqui só reproduzimos a resposta para ensaio.
import type { MotivoGuardrail } from "../agente/tipos";

export interface Bloqueio {
  motivo: MotivoGuardrail;
  texto: string;
  respostas_rapidas: string[];
  /** Guardrail visual (AlertaGuardrail) ou só recusa em texto (E2). */
  alerta: boolean;
}

/** Minúsculas e sem acentos, para casar as frases do cliente. */
export function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

const CONTINUAR = "Quer continuar o plano do apartamento?";
const RESPOSTAS_CONTINUAR = ["Continuar o plano", "O que você pode fazer?"];

// BUG-01: atividade ilícita. Dois grupos, sobre o texto já normalizado:
// (a) termos sem uso legítimo neste domínio; (b) verbo ilícito com intenção em
// primeira pessoa. Relato de vítima ("fui roubado", "sofri um golpe") fica de
// fora: os verbos são pedidos no infinitivo e "golpe" só conta com "dar/aplicar".
const TERMOS_ILICITOS =
  /\b(trafico de (pessoas|drogas|armas|orgaos)|trafic(ar|ando)|lav(agem de dinheiro|ar dinheiro)|caixa dois|piramide financeira|esquema ponzi|soneg(ar|acao|ando)|agiotagem|estelionato|propina|suborno|contrabando|falsificar (documento|nota|assinatura)\w*)\b/;

const PEDIDO_ILICITO =
  /\b(quero|queria|gostaria|preciso|como (eu )?(posso|faco)|me ajuda a|plano (para|pra)|jeito de)\b[^.!?]*\b(roubar|assaltar|furtar|fraudar|(dar|aplicar) um golpe|sequestrar|enganar o (banco|fisco|leao))\b/;

const REGRAS: { motivo: MotivoGuardrail; padrao: RegExp; texto: string; respostas: string[]; alerta: boolean }[] = [
  {
    motivo: "atividade_ilicita",
    padrao: new RegExp(`${TERMOS_ILICITOS.source}|${PEDIDO_ILICITO.source}`),
    texto:
      "Não consigo ajudar com isso. Trabalho só com objetivos financeiros legítimos, usando os seus dados. Se quiser, seguimos com o seu plano.",
    respostas: RESPOSTAS_CONTINUAR,
    alerta: true,
  },
  {
    motivo: "ignorar_instrucoes",
    padrao:
      /\b(ignor[ae]\w*|esquec[ae]\w*|desconsider[ae]\w*)\b.*\b(instruc\w*|regras?|prompt)\b|\b(system prompt|prompt do sistema|modo desenvolvedor|jailbreak)\b/,
    texto: `Não posso fazer isso. Só consigo usar os seus dados, e só para o seu objetivo. ${CONTINUAR}`,
    respostas: RESPOSTAS_CONTINUAR,
    alerta: true,
  },
  {
    motivo: "outro_cliente",
    padrao: /\b(outr[oa]s? (cliente|pessoa|usuari[oa]|conta)s?|dados d[aeo]s? (meu|minha) (pai|mae|irma|irmao|esposa|marido|vizinh[oa]|chefe))\b/,
    texto: `Não posso fazer isso. Só consigo usar os seus dados, e só para o seu objetivo. ${CONTINUAR}`,
    respostas: RESPOSTAS_CONTINUAR,
    alerta: true,
  },
  {
    motivo: "infra",
    padrao: /\b(sql|bigquery|tabelas? (internas?|do sistema|do banco)|banco de dados|credencia\w*|api key|chave de api|token|senha)\b/,
    texto: `Não posso compartilhar detalhes técnicos, credenciais ou acesso aos sistemas. ${CONTINUAR}`,
    respostas: RESPOSTAS_CONTINUAR,
    alerta: true,
  },
  {
    motivo: "compartilhar_dados",
    padrao: /\b(compartilh\w*|envi[ae]\w*|mand[ae]\w*)\b.*\b(dados|extrato)\b.*\b(para|pra|com)\b/,
    texto: `Não compartilho seus dados com ninguém, nem com outros bancos. ${CONTINUAR}`,
    respostas: RESPOSTAS_CONTINUAR,
    alerta: true,
  },
  {
    motivo: "promessa_credito",
    padrao: /\b(aprovad[oa]|aprovacao|aprovar|garant\w*)\b.*\b(financiamento|credito|emprestimo)\b|\b(financiamento|credito|emprestimo)\b.*\b(aprovad[oa]|aprovacao|aprovar|garant\w*)\b/,
    texto:
      "Não consigo garantir aprovação de crédito, porque isso depende de uma análise do banco. Posso simular um financiamento genérico, sem taxas, só como referência.",
    respostas: ["Simular um financiamento", "Continuar o plano"],
    alerta: false,
  },
];

export function detectarGuardrail(texto: string): Bloqueio | null {
  const t = normalizar(texto);
  for (const r of REGRAS) {
    if (r.padrao.test(t)) return { motivo: r.motivo, texto: r.texto, respostas_rapidas: r.respostas, alerta: r.alerta };
  }
  return null;
}
