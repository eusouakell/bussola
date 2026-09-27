"""Envelopes §5, códigos de erro locais e textos ao cliente do acompanhamento (pt-BR)."""

from collections.abc import Mapping
from typing import Any

from bussola_agent.mcp_conexao import ERRO_ENTRADA_INVALIDA, ERRO_INDISPONIVEL, MSG_INDISPONIVEL

# Códigos locais do agente (contratos §6, ACOMPANHAR e AGIR).
ERROR_NO_ACTIVE_PLAN = "SEM_PLANO_ATIVO"
ERROR_END_OF_REPLAY = "FIM_DO_REPLAY"
ERROR_CONSENT_REQUIRED = "CONSENTIMENTO_NECESSARIO"
ERROR_INVALID_INPUT = ERRO_ENTRADA_INVALIDA
ERROR_UNAVAILABLE = ERRO_INDISPONIVEL

MSG_NO_ACTIVE_PLAN = "Para acompanhar mês a mês, primeiro precisamos criar o seu plano."
MSG_END_OF_REPLAY = "Chegamos ao fim da demonstração: os dados vão até dezembro de 2025."
MSG_CONSENT_REQUIRED = (
    "Essa ação precisa da sua autorização. Peça o consentimento antes de ajustar o plano."
)
MSG_NO_ROUTE = (
    "Ainda não há uma rota recalculada. Avance um mês para ver se o plano precisa de ajuste."
)
MSG_WHICH_ROUTE = "Qual rota você quer adotar? Informe a rota A ou a rota B."
MSG_UNAVAILABLE = MSG_INDISPONIVEL

WARNING_REPLAY = (
    "O avanço do mês é uma simulação sobre dados históricos sintéticos de 2025: "
    "nenhum dado posterior ao mês revelado é usado."
)
WARNING_LOCAL_ROUTE = (
    "Rota calculada pela mesma regra da simulação de objetivo (sem rendimento), "
    "com a capacidade mensal informada pela ferramenta."
)
WARNING_CATEGORY_UNAVAILABLE = (
    "Não foi possível comparar os gastos do mês com a média anterior ao plano agora."
)


def warning_route_unavailable(route_id: str) -> str:
    return f"Não foi possível recalcular a rota {route_id} agora."


def error(code: str, message: str) -> dict[str, Any]:
    return {"erro": {"codigo": code, "mensagem": message}}


def error_code(envelope: Mapping[str, Any] | None) -> str | None:
    """Código do envelope de erro, ou ``None`` se for sucesso."""
    if not isinstance(envelope, Mapping):
        return ERROR_UNAVAILABLE
    err = envelope.get("erro")
    if isinstance(err, Mapping):
        code = err.get("codigo")
        return code if isinstance(code, str) and code else ERROR_UNAVAILABLE
    if not isinstance(envelope.get("dados"), Mapping):
        return ERROR_UNAVAILABLE
    return None


def period_end(envelope: Mapping[str, Any]) -> int | None:
    fonte = envelope.get("fonte")
    periodo = fonte.get("periodo") if isinstance(fonte, Mapping) else None
    fim = periodo.get("fim") if isinstance(periodo, Mapping) else None
    return fim if isinstance(fim, int) and not isinstance(fim, bool) else None


def within_cut(envelope: Mapping[str, Any], cut: int) -> bool:
    """True se o envelope não traz período depois do corte ``cut``."""
    end = period_end(envelope)
    return end is None or end <= cut


def warnings_of(envelope: Mapping[str, Any]) -> list[str]:
    avisos = envelope.get("avisos")
    return [a for a in avisos if isinstance(a, str)] if isinstance(avisos, list) else []
