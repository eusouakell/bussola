// Auditoria derivada dos eventos do agente (R8). Tipos de contratos §6.
import type { Consentimento, EstadoJornada, EstadoSessao, MotivoGuardrail, RespostaFerramenta } from "../agente/tipos";
import { mascararId } from "../formatacao/formatar";
import type { EventoAuditoria, TipoEventoAuditoria } from "./modelo";

function evento(
  tipo_evento: TipoEventoAuditoria,
  ts: number,
  estado: EstadoJornada | undefined,
  resumo: string,
): EventoAuditoria {
  return { tipo_evento, ts, estado_jornada: estado, resumo };
}

export function auditoriaInicio(ts: number, estado: EstadoSessao): EventoAuditoria[] {
  return [evento("sessao_iniciada", ts, estado.estado_jornada, "sessão da demonstração")];
}

export function auditoriaChamada(nome: string, ts: number, estado: EstadoSessao): EventoAuditoria[] {
  return [evento("ferramenta_chamada", ts, estado.estado_jornada, nome)];
}

export function auditoriaResposta(
  nome: string,
  resposta: RespostaFerramenta,
  ts: number,
  estado: EstadoSessao,
): EventoAuditoria[] {
  const jornada = estado.estado_jornada;
  if (resposta.tipo === "erro") return [];
  const dados = resposta.tipo === "envelope" ? resposta.envelope.dados : resposta.dados;
  switch (nome) {
    case "criar_plano":
      return [
        evento("plano_criado", ts, jornada, dados.plano_id ? `plano ${mascararId(String(dados.plano_id))}` : "plano"),
        evento("acao_executada", ts, jornada, "criar_plano · ok"),
      ];
    case "ativar_lembretes":
    case "simular_contratacao":
      return [evento("acao_executada", ts, jornada, `${nome} · ok`)];
    case "ajustar_plano":
      return [
        evento("plano_ajustado", ts, jornada, `rota ${String(dados.rota ?? "")}`.trim()),
        evento("acao_executada", ts, jornada, "ajustar_plano · ok"),
      ];
    case "avancar_mes": {
      const saida = [evento("acompanhamento_mes_avancado", ts, jornada, `${String(dados.anomes ?? "")} · ${String(dados.status ?? "")}`)];
      if (dados.status === "desvio") {
        const macro = (dados.categoria_desvio as { macro?: string } | null)?.macro;
        saida.push(evento("desvio_detectado", ts, jornada, macro ? `causa: ${macro}` : "desvio"));
        if (Array.isArray(dados.rotas) && dados.rotas.length > 0) {
          saida.push(evento("rota_recalculada", ts, jornada, `${dados.rotas.length} rotas`));
        }
      }
      return saida;
    }
    default:
      return [];
  }
}

function nomeEstado(estado: EstadoJornada | undefined): string {
  return (estado ?? "início").toLowerCase();
}

/** Diferenças de state que viram auditoria (jornada e consentimentos). */
export function auditoriaEstado(antes: EstadoSessao, depois: EstadoSessao, ts: number): EventoAuditoria[] {
  const saida: EventoAuditoria[] = [];
  if (depois.estado_jornada && depois.estado_jornada !== antes.estado_jornada) {
    saida.push(
      evento(
        "estado_alterado",
        ts,
        depois.estado_jornada,
        `${nomeEstado(antes.estado_jornada)} → ${nomeEstado(depois.estado_jornada)}`,
      ),
    );
  }
  const anteriores: Record<string, Consentimento> = antes.consentimentos ?? {};
  for (const [acao, c] of Object.entries(depois.consentimentos ?? {})) {
    const anterior = anteriores[acao];
    const mesmoPedido = anterior?.consent_id === c.consent_id;
    if (c.status === "pendente" && (!mesmoPedido || anterior?.status !== "pendente")) {
      saida.push(evento("consentimento_solicitado", ts, depois.estado_jornada, `${acao} · pendente`));
    } else if (c.status !== "pendente" && (!mesmoPedido || anterior?.status !== c.status)) {
      saida.push(evento("consentimento_decidido", ts, depois.estado_jornada, `${acao} · ${c.status}`));
    }
  }
  return saida;
}

export function auditoriaGuardrail(motivo: MotivoGuardrail, ts: number, estado: EstadoSessao): EventoAuditoria[] {
  return [evento("guardrail_bloqueio", ts, estado.estado_jornada, motivo)];
}
