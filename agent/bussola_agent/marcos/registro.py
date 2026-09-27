"""Callback ``after_tool`` de ordem 30: grava ``marcos`` no ``session.state``.

Contratos §6 reserva a ordem 30 ao ciclo 009. O callback só observa: devolve
sempre ``None``, então nunca substitui o resultado da ferramenta nem interrompe
a cadeia de callbacks.

Não há ferramenta ADK local no 009 — ``planejar_marcos`` é a ferramenta do MCP,
já exposta ao modelo pelo ``McpToolset``
(``specs/009-marcos-financeiros/research.md`` R8).
"""

from typing import Any

from bussola_agent.estado import CHAVE_MARCOS
from bussola_agent.logging_json import obter_logger

FERRAMENTA = "planejar_marcos"
ORDEM = 30

_log = obter_logger(__name__)


def _nome_da_ferramenta(tool: Any) -> str | None:
    nome = getattr(tool, "name", None)
    return nome if isinstance(nome, str) else None


def _dados_do_envelope(resposta: Any) -> dict[str, Any] | None:
    """``dados`` do envelope §5, ou ``None`` para erro e resposta fora do contrato."""
    if not isinstance(resposta, dict) or "erro" in resposta:
        return None
    dados = resposta.get("dados")
    return dados if isinstance(dados, dict) else None


def gravar_marcos(
    tool: Any = None,
    args: dict[str, Any] | None = None,
    tool_context: Any = None,
    tool_response: Any = None,
    **_: Any,
) -> None:
    """Guarda o último ``dados`` de ``planejar_marcos`` em ``session.state["marcos"]``."""
    if _nome_da_ferramenta(tool) != FERRAMENTA or tool_context is None:
        return None
    dados = _dados_do_envelope(tool_response)
    if dados is None:
        return None
    # Reatribui a chave: o State do ADK só registra o delta em __setitem__.
    tool_context.state[CHAVE_MARCOS] = dict(dados)
    _log.info(
        "Marcos gravados no state.",
        extra={"evento": "marcos_registrados", "ferramenta": FERRAMENTA},
    )
    return None
