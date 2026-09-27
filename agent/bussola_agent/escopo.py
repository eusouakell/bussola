"""Session scope and tool bookkeeping callbacks (004 §3.4, §3.5; spec FR-011–FR-013).

- :func:`initialize_session` (``before_agent_callback``): fills the missing
  keys of contratos §6 from ``ANCHOR_USER_ID`` and ``REPLAY_START_ANOMES``.
- :func:`enforce_scope` (``before_tool``, order 10): MCP tools always leave
  with ``id_usuario`` and ``ate_anomes`` from ``session.state``, and the tools
  that take the goal amount leave with the ``valor_alvo`` that
  ``registrar_objetivo`` recorded. What the model sent is ignored; a divergent
  id is logged without echoing it.
- :func:`record_tool_result` (``after_tool``, order 10): the ``fonte`` of MCP
  tools goes to ``ultimas_fontes`` and the journey advances
  (:mod:`bussola_agent.jornada.progress`).

Registered by ``agent.py`` in the frozen chain of :mod:`bussola_agent.callbacks`.
"""

from collections.abc import Mapping
from typing import Any

from google.adk.tools.mcp_tool.mcp_tool import McpTool

from bussola_agent import config
from bussola_agent.estado import (
    CHAVE_ATE_ANOMES,
    CHAVE_ID_USUARIO,
    CHAVE_OBJETIVO,
    adicionar_fonte,
    estado_inicial,
)
from bussola_agent.jornada.progress import apply_tool_outcome
from bussola_agent.jornada.tool_results import extract_envelope, succeeded
from bussola_agent.logging_json import obter_logger
from bussola_agent.mcp_conexao import (
    ERRO_ENTRADA_INVALIDA,
    FERRAMENTAS_MCP,
    MSG_ESCOPO_INVALIDO,
    aplicar_escopo,
)

ORDER = 10
# Defaults do escopo âncora: de :mod:`bussola_agent.config`, a fonte única.
DEFAULT_ANCHOR_USER_ID = config.ANCHOR_USER_ID_PADRAO
DEFAULT_REPLAY_START = config.REPLAY_START_PADRAO
SCOPE_KEYS: tuple[str, ...] = (CHAVE_ID_USUARIO, CHAVE_ATE_ANOMES)

# MCP tools that take the customer's goal amount (contratos §5). The goal is
# registered by ``registrar_objetivo``; the model never restates it.
KEY_TARGET_VALUE = "valor_alvo"
TARGET_VALUE_TOOLS: frozenset[str] = frozenset(
    {"simular_objetivo", "comparar_cenarios", "planejar_marcos"}
)

EVENT_SCOPE_OVERRIDDEN = "escopo_sobrescrito"
EVENT_SCOPE_INVALID = "escopo_invalido"
ERROR_DIVERGENT_USER = "ID_USUARIO_DIVERGENTE"
ERROR_DIVERGENT_MONTH = "ATE_ANOMES_DIVERGENTE"
ERROR_DIVERGENT_TARGET = "VALOR_ALVO_DIVERGENTE"

_log = obter_logger(__name__)


def _session_id(context: Any) -> str | None:
    session = getattr(context, "session", None)
    value = getattr(session, "id", None)
    return value if isinstance(value, str) else None


async def initialize_session(callback_context: Any) -> None:
    """Fills the §6 keys missing from ``session.state`` (``before_agent_callback``).

    ``id_usuario`` comes from ``ANCHOR_USER_ID`` and ``ate_anomes`` from
    ``REPLAY_START_ANOMES``. Keys already present are kept, except a ``None``
    scope. With invalid configuration it logs the error and leaves the state
    alone (MCP tools then answer ``ENTRADA_INVALIDA``).
    """
    state = callback_context.state
    try:
        initial = estado_inicial(config.anchor_user_id(), config.replay_start_anomes())
    except ValueError:
        _log.error(
            "ANCHOR_USER_ID ou REPLAY_START_ANOMES inválido.",
            extra={"evento": "sessao_sem_escopo", "erro_codigo": "CONFIGURACAO_INVALIDA"},
        )
        return None
    missing = [
        key for key in initial if key not in state or (key in SCOPE_KEYS and state.get(key) is None)
    ]
    for key in missing:
        state[key] = initial[key]
    if missing:
        _log.info(
            "Estado da sessão inicializado.",
            extra={
                "evento": "sessao_iniciada",
                "session_id": _session_id(callback_context),
                "ate_anomes": state.get(CHAVE_ATE_ANOMES),
            },
        )
    return None


def is_mcp_tool(tool: Any) -> bool:
    """True for tools served by ``bussola-mcp`` (``McpTool`` or a contract §5 name)."""
    return isinstance(tool, McpTool) or getattr(tool, "name", None) in FERRAMENTAS_MCP


def _same_user(sent: object, scoped: str) -> bool:
    return isinstance(sent, str) and sent.strip().lower() == scoped


def _same_month(sent: object, scoped: int) -> bool:
    if isinstance(sent, bool):
        return False
    try:
        return int(str(sent).strip()) == scoped
    except ValueError:
        return False


def _registered_target(state: Any) -> float | None:
    """``valor_alvo`` of the goal in ``session.state``, or ``None`` when unset."""
    goal = state.get(CHAVE_OBJETIVO)
    value = goal.get(KEY_TARGET_VALUE) if isinstance(goal, Mapping) else None
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    return round(float(value), 2)


def _same_target(sent: object, scoped: float) -> bool:
    if isinstance(sent, bool):
        return False
    try:
        return round(float(str(sent).strip()), 2) == scoped
    except ValueError:
        return False


def enforce_scope(tool: Any, args: dict[str, Any], tool_context: Any) -> dict[str, Any] | None:
    """``before_tool`` order 10: overwrites the MCP scope in place with the state values.

    ``id_usuario`` and ``ate_anomes`` always come from the state. For the tools
    of :data:`TARGET_VALUE_TOOLS`, so does ``valor_alvo`` whenever the goal is
    registered, so a simulation can never answer for an amount the customer did
    not ask for. The amount itself is never logged (contratos §9).

    Returns the ``ENTRADA_INVALIDA`` envelope (the tool is skipped) when the
    state has no valid scope; otherwise ``None`` so the chain continues.
    """
    if not is_mcp_tool(tool):
        return None
    name = getattr(tool, "name", None)
    base = {"ferramenta": name, "session_id": _session_id(tool_context)}
    try:
        scoped = aplicar_escopo(args, tool_context.state)
    except ValueError:
        _log.warning(
            "Chamada MCP sem escopo válido no state.",
            extra={**base, "evento": EVENT_SCOPE_INVALID, "erro_codigo": ERRO_ENTRADA_INVALIDA},
        )
        return {"erro": {"codigo": ERRO_ENTRADA_INVALIDA, "mensagem": MSG_ESCOPO_INVALIDO}}

    sent_user = args.get(CHAVE_ID_USUARIO)
    if sent_user is not None and not _same_user(sent_user, scoped[CHAVE_ID_USUARIO]):
        _log.warning(
            "O modelo enviou outro id_usuario; o escopo da sessão foi aplicado.",
            extra={**base, "evento": EVENT_SCOPE_OVERRIDDEN, "erro_codigo": ERROR_DIVERGENT_USER},
        )
    sent_month = args.get(CHAVE_ATE_ANOMES)
    if sent_month is not None and not _same_month(sent_month, scoped[CHAVE_ATE_ANOMES]):
        _log.info(
            "O modelo enviou outro ate_anomes; o escopo da sessão foi aplicado.",
            extra={
                **base,
                "evento": EVENT_SCOPE_OVERRIDDEN,
                "erro_codigo": ERROR_DIVERGENT_MONTH,
                "ate_anomes": scoped[CHAVE_ATE_ANOMES],
            },
        )
    target = _registered_target(tool_context.state) if name in TARGET_VALUE_TOOLS else None
    if target is not None:
        sent_target = args.get(KEY_TARGET_VALUE)
        if sent_target is not None and not _same_target(sent_target, target):
            _log.warning(
                "O modelo enviou outro valor_alvo; o objetivo registrado foi aplicado.",
                extra={
                    **base,
                    "evento": EVENT_SCOPE_OVERRIDDEN,
                    "erro_codigo": ERROR_DIVERGENT_TARGET,
                },
            )
        scoped[KEY_TARGET_VALUE] = target
    args.update(scoped)
    return None


def record_tool_result(
    tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any
) -> None:
    """``after_tool`` order 10: records the MCP ``fonte`` and advances the journey.

    Never replaces the tool response (always returns ``None``).
    """
    name = getattr(tool, "name", None) or ""
    state = tool_context.state
    if is_mcp_tool(tool) and succeeded(tool_response):
        source = (extract_envelope(tool_response) or {}).get("fonte")
        if isinstance(source, Mapping):
            adicionar_fonte(state, source)
    apply_tool_outcome(state, name, tool_response, session_id=_session_id(tool_context))
    return None
