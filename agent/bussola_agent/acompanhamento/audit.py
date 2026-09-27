"""Eventos de auditoria e linhas de acompanhamento do 006.

Os resumos levam só identificadores, meses, status e valores já calculados
(nunca texto do cliente nem prompt). Falha do registro não quebra a
ferramenta: vira um log de aviso com os campos permitidos (contratos §9).
"""

from collections.abc import Mapping
from typing import Any

from bussola_agent.estado import EstadoJornada
from bussola_agent.logging_json import obter_logger
from bussola_agent.persistencia import Acompanhamento, EventoAuditoria, RegistroApp, TipoEvento

logger = obter_logger(__name__)

ACTION_ROUTE_RECALCULATED = "rota_recalculada"
ACTION_REVIEW_PLAN = "revisar_plano"
ACTION_KEEP_OR_ANTICIPATE = "manter_ou_antecipar"
ACTION_KEEP_PLAN = "manter_plano"


def record_event(
    registry: RegistroApp,
    *,
    session_id: str,
    estado: EstadoJornada,
    tipo: TipoEvento,
    ferramenta: str,
    resumo: Mapping[str, Any],
) -> bool:
    """Grava um ``EventoAuditoria``. Devolve ``False`` (e loga) se o registro falhar."""
    try:
        registry.registrar_evento(
            EventoAuditoria(
                session_id=session_id,
                estado=estado,
                tipo_evento=tipo,
                ferramenta=ferramenta,
                resumo=dict(resumo),
            )
        )
    except Exception:  # auditoria não pode derrubar a ferramenta
        logger.warning(
            "falha ao gravar evento de auditoria",
            extra={
                "session_id": session_id,
                "ferramenta": ferramenta,
                "evento": str(tipo),
                "erro_codigo": "REGISTRO_INDISPONIVEL",
            },
        )
        return False
    logger.info(
        "evento de acompanhamento",
        extra={
            "session_id": session_id,
            "estado_jornada": str(estado),
            "ferramenta": ferramenta,
            "evento": str(tipo),
        },
    )
    return True


def record_follow_up(
    registry: RegistroApp,
    *,
    session_id: str,
    row: Mapping[str, Any],
) -> bool:
    """Grava a linha da tabela ``acompanhamento``. Devolve ``False`` (e loga) se falhar."""
    try:
        registry.registrar_acompanhamento(Acompanhamento(**dict(row)))
    except Exception:  # idem
        logger.warning(
            "falha ao gravar acompanhamento",
            extra={
                "session_id": session_id,
                "ferramenta": "avancar_mes",
                "erro_codigo": "REGISTRO_INDISPONIVEL",
            },
        )
        return False
    return True


def suggested_action(status: str, has_routes: bool) -> str:
    """``acao_sugerida`` da linha de acompanhamento, pelo status do mês."""
    if status == "desvio":
        return ACTION_ROUTE_RECALCULATED if has_routes else ACTION_REVIEW_PLAN
    if status == "folga":
        return ACTION_KEEP_OR_ANTICIPATE
    return ACTION_KEEP_PLAN
