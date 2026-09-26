// Reducer puro: eventos do agente → modelo da tela (data-model.md).
import { dadosDe, extrairEnvelope } from "../agente/envelope";
import type { Dados, EstadoSessao, EventoAdk, RespostaFerramenta } from "../agente/tipos";
import { mascararArgs } from "../formatacao/formatar";
import { auditoriaChamada, auditoriaEstado, auditoriaGuardrail, auditoriaInicio, auditoriaResposta } from "./auditoria";
import { CATALOGO } from "./catalogo";
import {
  MODELO_INICIAL,
  type EventoAuditoria,
  type ItemCard,
  type ItemConversa,
  type ItemFerramenta,
  type ItemMensagemAgente,
  type ModeloSessao,
  type RegistroFerramenta,
} from "./modelo";

export type AcaoSessao =
  | { tipo: "iniciada"; estado: EstadoSessao; eventos: EventoAdk[]; agora: number }
  | { tipo: "enviada"; texto: string; agora: number }
  | { tipo: "evento"; evento: EventoAdk; agora: number }
  | { tipo: "turno_fim"; estado?: EstadoSessao | null; agora: number }
  | { tipo: "falha"; mensagem: string; reenviar?: string; agora: number }
  | { tipo: "reiniciar" };

/** Ferramentas cujo erro vira aviso âmbar no diagnóstico (§4.1). */
const DIAGNOSTICO = new Set(["perfil_financeiro", "capacidade_poupanca"]);

/** Merge raso do ADK; chaves `temp:*` não são estado de sessão. */
export function aplicarDelta(estado: EstadoSessao, delta: Dados | undefined): EstadoSessao {
  if (!delta) return estado;
  const novo: EstadoSessao = { ...estado };
  for (const [chave, valor] of Object.entries(delta)) {
    if (chave.startsWith("temp:")) continue;
    novo[chave] = valor;
  }
  return novo;
}

class Rascunho {
  m: ModeloSessao;
  constructor(m: ModeloSessao) {
    this.m = { ...m, itens: [...m.itens], auditoria: [...m.auditoria], ferramentas: [...m.ferramentas] };
  }
  chave(): string {
    this.m.seq += 1;
    return `i${this.m.seq}`;
  }
  auditar(eventos: EventoAuditoria[]) {
    this.m.auditoria.push(...eventos);
  }
  mudarEstado(novo: EstadoSessao, ts: number) {
    const antes = this.m.estado;
    this.auditar(auditoriaEstado(antes, novo, ts));
    if (novo.estado_jornada && novo.estado_jornada !== antes.estado_jornada) {
      this.m.jornada = [...this.m.jornada, { estado: novo.estado_jornada, ts }];
    }
    this.m.estado = novo;
  }
  substituir(indice: number, item: ItemConversa) {
    this.m.itens[indice] = item;
  }
}

function indiceFerramenta(itens: ItemConversa[], id: string | undefined, nome: string): number {
  if (id) {
    const porId = itens.findIndex((i) => i.tipo === "ferramenta" && i.chamadaId === id);
    if (porId >= 0) return porId;
  }
  for (let i = itens.length - 1; i >= 0; i -= 1) {
    const item = itens[i];
    if (item.tipo === "ferramenta" && item.nome === nome && item.status === "consultando") return i;
  }
  return -1;
}

function novoCard(
  r: Rascunho,
  componente: string,
  nome: string,
  chamadaId: string,
  resposta: RespostaFerramenta,
  ts: number,
  recomendado?: string,
): ItemCard {
  return {
    tipo: "card",
    chave: r.chave(),
    ts,
    turno: r.m.turno,
    componente,
    nome,
    chamadaId,
    resposta,
    complementos: {},
    estado: r.m.estado,
    recomendado,
  };
}

function adicionarCards(
  r: Rascunho,
  nome: string,
  chamadaId: string,
  args: Dados,
  resposta: RespostaFerramenta,
  ts: number,
  recomendado?: string,
) {
  if (resposta.tipo === "erro") {
    if (resposta.codigo === "DADOS_INSUFICIENTES" && DIAGNOSTICO.has(nome)) {
      juntarDiagnostico(r, nome, chamadaId, resposta, ts);
    }
    return;
  }
  const dados = dadosDe(resposta);
  if (nome === "solicitar_consentimento") {
    const acao = String(dados.acao ?? args.acao ?? "");
    const consentId = String(dados.consent_id ?? r.m.estado.consentimentos?.[acao]?.consent_id ?? chamadaId);
    const indice = r.m.itens.findIndex((i) => i.tipo === "consentimento" && i.consentId === consentId);
    if (indice < 0) {
      r.m.itens.push({ tipo: "consentimento", chave: r.chave(), ts, acao, consentId, pedido: dados });
    } else {
      const item = r.m.itens[indice];
      if (item.tipo === "consentimento") r.substituir(indice, { ...item, pedido: { ...item.pedido, ...dados } });
    }
    return;
  }
  if (nome === "avancar_mes") {
    if (typeof dados.anomes === "number") r.m.itens.push({ tipo: "divisor_mes", chave: r.chave(), ts, anomes: dados.anomes });
    r.m.itens.push(novoCard(r, "CardPlanejadoRealizado", nome, chamadaId, resposta, ts));
    if (dados.status === "desvio" && Array.isArray(dados.rotas) && dados.rotas.length > 0) {
      r.m.itens.push(novoCard(r, "CardRotaRecalculada", nome, chamadaId, resposta, ts));
    } else if (dados.status === "folga") {
      r.m.itens.push(novoCard(r, "CardOportunidade", nome, chamadaId, resposta, ts));
    }
    return;
  }
  if (DIAGNOSTICO.has(nome)) {
    juntarDiagnostico(r, nome, chamadaId, resposta, ts);
    return;
  }
  const componente = CATALOGO[nome]?.card;
  if (componente) r.m.itens.push(novoCard(r, componente, nome, chamadaId, resposta, ts, recomendado));
}

/** Perfil e capacidade do mesmo turno formam um único `CardDiagnostico`. */
function juntarDiagnostico(r: Rascunho, nome: string, chamadaId: string, resposta: RespostaFerramenta, ts: number) {
  const indice = r.m.itens.findIndex(
    (i) => i.tipo === "card" && i.componente === "CardDiagnostico" && i.turno === r.m.turno && i.nome !== nome && !(nome in i.complementos),
  );
  if (indice >= 0) {
    const card = r.m.itens[indice] as ItemCard;
    r.substituir(indice, { ...card, complementos: { ...card.complementos, [nome]: resposta } });
    return;
  }
  r.m.itens.push(novoCard(r, "CardDiagnostico", nome, chamadaId, resposta, ts));
}

/** Consentimento pendente no state sem card na conversa: o card nasce do state (§4.1). */
function consentimentosPendentes(r: Rascunho, ts: number) {
  for (const [acao, c] of Object.entries(r.m.estado.consentimentos ?? {})) {
    if (c.status !== "pendente") continue;
    const existe = r.m.itens.some((i) => i.tipo === "consentimento" && i.consentId === c.consent_id);
    if (!existe) r.m.itens.push({ tipo: "consentimento", chave: r.chave(), ts, acao, consentId: c.consent_id });
  }
}

function ultimoAgenteDoTurno(r: Rascunho): number {
  for (let i = r.m.itens.length - 1; i >= 0; i -= 1) {
    const item = r.m.itens[i];
    if (item.tipo === "mensagem_cliente") return -1;
    if (item.tipo === "mensagem_agente") return i;
  }
  return -1;
}

function aplicarEvento(m: ModeloSessao, e: EventoAdk, agora: number): ModeloSessao {
  if (e.error) {
    const ultimaDoCliente = m.itens.findLast((i) => i.tipo === "mensagem_cliente");
    return falha(m, "Não consegui falar com a Bússola agora.", ultimaDoCliente?.texto, agora);
  }
  if (e.author === "user") return m;
  const r = new Rascunho(m);
  const ts = typeof e.timestamp === "number" ? e.timestamp * 1000 : agora;
  const partes = e.content?.parts ?? [];
  const meta = e.customMetadata?.bussola;

  // 1. state (os cards seguintes enxergam o state novo)
  if (e.actions?.stateDelta) {
    r.mudarEstado(aplicarDelta(r.m.estado, e.actions.stateDelta), ts);
    consentimentosPendentes(r, ts);
  }

  // 2. chamadas (eventos parciais só trazem texto; o evento final repete as chamadas)
  for (const parte of e.partial ? [] : partes) {
    const fc = parte.functionCall;
    if (!fc) continue;
    if (fc.id && r.m.itens.some((i) => i.tipo === "ferramenta" && i.chamadaId === fc.id)) continue;
    const chamadaId = fc.id ?? `${fc.name}-${r.m.seq + 1}`;
    const args = mascararArgs(fc.args);
    const item: ItemFerramenta = {
      tipo: "ferramenta",
      chave: r.chave(),
      ts,
      chamadaId,
      nome: fc.name,
      args,
      status: "consultando",
      inicio: ts,
      turno: r.m.turno,
    };
    r.m.itens.push(item);
    r.m.ferramentas.push({ chamadaId, nome: fc.name, args, status: "consultando", inicio: ts, avisos: [] });
    r.auditar(auditoriaChamada(fc.name, ts, r.m.estado));
  }

  // 3. respostas
  for (const parte of e.partial ? [] : partes) {
    const fr = parte.functionResponse;
    if (!fr) continue;
    if (fr.id && r.m.itens.some((i) => i.tipo === "ferramenta" && i.chamadaId === fr.id && i.status !== "consultando")) continue;
    const resposta = extrairEnvelope(fr.response);
    const status = resposta.tipo === "erro" ? "erro" : "ok";
    let indice = indiceFerramenta(r.m.itens, fr.id, fr.name);
    if (indice < 0) {
      const chamadaId = fr.id ?? `${fr.name}-${r.m.seq + 1}`;
      r.m.itens.push({
        tipo: "ferramenta",
        chave: r.chave(),
        ts,
        chamadaId,
        nome: fr.name,
        args: {},
        status: "consultando",
        inicio: ts,
        turno: r.m.turno,
      });
      r.m.ferramentas.push({ chamadaId, nome: fr.name, args: {}, status: "consultando", inicio: ts, avisos: [] });
      indice = r.m.itens.length - 1;
    }
    const item = r.m.itens[indice] as ItemFerramenta;
    r.substituir(indice, { ...item, status, resposta, fim: ts });
    const reg = r.m.ferramentas.findIndex((f) => f.chamadaId === item.chamadaId);
    if (reg >= 0) {
      const atual: RegistroFerramenta = r.m.ferramentas[reg];
      r.m.ferramentas[reg] = {
        ...atual,
        status,
        fim: ts,
        fonte: resposta.tipo === "envelope" ? resposta.envelope.fonte : undefined,
        avisos: resposta.tipo === "envelope" ? resposta.envelope.avisos : [],
        codigoErro: resposta.tipo === "erro" ? resposta.codigo : undefined,
      };
    }
    r.auditar(auditoriaResposta(fr.name, resposta, ts, r.m.estado));
    adicionarCards(r, fr.name, item.chamadaId, item.args, resposta, ts, meta?.recomendado);
  }

  // 4. texto
  const textos = partes.filter((p) => typeof p.text === "string" && !p.thought).map((p) => p.text as string);
  const autor = e.author || "bussola";
  const rascunho = r.m.rascunhos[autor];
  if (textos.length > 0 && e.partial) {
    const texto = (rascunho?.texto ?? "") + textos.join("");
    if (rascunho) {
      const indice = r.m.itens.findIndex((i) => i.chave === rascunho.chave);
      if (indice >= 0) r.substituir(indice, { ...(r.m.itens[indice] as ItemMensagemAgente), texto });
      r.m.rascunhos = { ...r.m.rascunhos, [autor]: { chave: rascunho.chave, texto } };
    } else {
      const chave = r.chave();
      r.m.itens.push({ tipo: "mensagem_agente", chave, ts, autor, texto, emStreaming: true });
      r.m.rascunhos = { ...r.m.rascunhos, [autor]: { chave, texto } };
    }
  } else if (textos.length > 0) {
    const texto = textos.join("");
    const semRascunho = { ...r.m.rascunhos };
    delete semRascunho[autor];
    r.m.rascunhos = semRascunho;
    const indice = rascunho ? r.m.itens.findIndex((i) => i.chave === rascunho.chave) : -1;
    if (meta?.guardrail) {
      if (indice >= 0) r.m.itens.splice(indice, 1);
      r.m.itens.push({
        tipo: "guardrail",
        chave: r.chave(),
        ts,
        motivo: meta.guardrail,
        texto,
        respostasRapidas: meta.respostas_rapidas,
      });
      r.auditar(auditoriaGuardrail(meta.guardrail, ts, r.m.estado));
    } else {
      const mensagem: ItemMensagemAgente = {
        tipo: "mensagem_agente",
        chave: indice >= 0 ? (r.m.itens[indice] as ItemMensagemAgente).chave : r.chave(),
        ts,
        autor,
        texto,
        emStreaming: false,
        tag: meta?.tag,
        respostasRapidas: meta?.respostas_rapidas,
      };
      if (indice >= 0) {
        // o texto final substitui o rascunho e vai para o fim (depois dos cards do turno)
        r.m.itens.splice(indice, 1);
      }
      r.m.itens.push(mensagem);
    }
  } else if (meta && !e.partial) {
    if (meta.guardrail) r.auditar(auditoriaGuardrail(meta.guardrail, ts, r.m.estado));
    if (meta.respostas_rapidas || meta.tag) {
      const indice = ultimoAgenteDoTurno(r);
      if (indice >= 0) {
        const msg = r.m.itens[indice] as ItemMensagemAgente;
        r.substituir(indice, {
          ...msg,
          tag: meta.tag ?? msg.tag,
          respostasRapidas: meta.respostas_rapidas ?? msg.respostasRapidas,
        });
      }
    }
  }
  return r.m;
}

function falha(m: ModeloSessao, mensagem: string, reenviar: string | undefined, agora: number): ModeloSessao {
  const r = new Rascunho(m);
  r.m.itens = r.m.itens
    .filter((i) => !(i.tipo === "mensagem_agente" && i.emStreaming && i.texto === ""))
    .map((i) => (i.tipo === "mensagem_agente" && i.emStreaming ? { ...i, emStreaming: false } : i));
  r.m.itens.push({ tipo: "falha_conexao", chave: r.chave(), ts: agora, mensagem, reenviar });
  r.m.rascunhos = {};
  r.m.ocupado = false;
  r.m.erroConexao = mensagem;
  return r.m;
}

export function reducerSessao(m: ModeloSessao, acao: AcaoSessao): ModeloSessao {
  switch (acao.tipo) {
    case "reiniciar":
      return MODELO_INICIAL;
    case "iniciada": {
      const r = new Rascunho({ ...MODELO_INICIAL });
      r.auditar(auditoriaInicio(acao.agora, acao.estado));
      r.mudarEstado(acao.estado, acao.agora);
      let saida = r.m;
      for (const evento of acao.eventos) saida = aplicarEvento(saida, evento, acao.agora);
      return saida;
    }
    case "enviada": {
      const r = new Rascunho(m);
      r.m.turno += 1;
      r.m.ocupado = true;
      r.m.erroConexao = undefined;
      r.m.itens.push({ tipo: "mensagem_cliente", chave: r.chave(), ts: acao.agora, texto: acao.texto });
      return r.m;
    }
    case "evento":
      return aplicarEvento(m, acao.evento, acao.agora);
    case "turno_fim": {
      const r = new Rascunho(m);
      r.m.itens = r.m.itens.map((i) => (i.tipo === "mensagem_agente" && i.emStreaming ? { ...i, emStreaming: false } : i));
      r.m.rascunhos = {};
      r.m.ocupado = false;
      if (acao.estado) r.mudarEstado(acao.estado, acao.agora);
      return r.m;
    }
    case "falha":
      return falha(m, acao.mensagem, acao.reenviar, acao.agora);
  }
}
